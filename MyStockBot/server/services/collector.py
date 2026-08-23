"""수집 루프 — 관심종목 시세·지표를 백그라운드에서 주기적으로 갱신해 인메모리 상태에 채운다.

GET /api/snapshot 은 이 모듈이 채운 상태(get_state)를 읽기만 한다(snapshot_cache.py).
수집 자체는 서버 전용 조립(_collect_one)이며, cron 전용 crawler.fetch_stock_price/fetch_all
경로와는 별개다(그쪽은 pipeline.py → src/main.py 가 그대로 사용, 이 모듈은 건드리지 않음).

사이클:
  1) db.load_watchlist() 로 활성 종목 로드.
  2) KIS 토큰 1회 발급 시도(실패하면 이번 사이클은 전 종목 yfinance 폴백 경로로만 진행).
  3) ThreadPoolExecutor(max_workers=4) 로 종목별 병렬 수집(_collect_one).
  4) 완료 후 상태를 원자적으로 통째로 교체(_state 참조 자체를 바꿔치기 + 락).

사이클 간격: 장중(평일 09:00~15:40 Asia/Seoul) COLLECTOR_INTERVAL_MARKET,
그 외 COLLECTOR_INTERVAL_IDLE. 부팅 직후 즉시 1회 수집.
"""
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

import crawler
import db
import indicators
import kis_auth
from config import (
    COLLECTOR_INTERVAL_IDLE,
    COLLECTOR_INTERVAL_MARKET,
    KIS_MINUTE_BACKFILL_DAYS,
    KIS_MINUTE_ENABLED,
    TIMEZONE,
)

from . import alerts

logger = logging.getLogger(__name__)

_MAX_WORKERS = 4

_MARKET_OPEN = dtime(9, 0)
_MARKET_CLOSE = dtime(15, 40)

# 재무데이터(PER/PBR/ROE/매출액/순이익)는 사이클마다 부르면 KIS 콜이 낭비되므로
# 코드당 6시간 in-memory 캐시(과설계 방지 — DB 테이블 없이 프로세스 메모리로 충분).
_FINANCIALS_TTL_SECONDS = 6 * 60 * 60
# 전 종목이 부팅 직후 같은 사이클에서 캐시를 채우면 정확히 6시간마다 전 종목이 동시에
# 만료되어 그 사이클만 KIS 콜이 튄다 — 종목별 ±10분 지터로 만료 시점을 분산.
_FINANCIALS_TTL_JITTER_SECONDS = 10 * 60

# 캔들 저장소 신선도 게이트(candles.py 의 read-through 기준과 동일 사상).
# 일봉+ 는 600초, 60분봉은 시간당 1회 갱신이면 충분하므로 분봉 일반 기준(60초)보다
# 여유 있는 임계치(5분)를 둔다 — 장중 30초 사이클마다 외부 재조회하지 않기 위함.
_DAILY_FRESH_SECONDS = 600
_60M_FRESH_SECONDS = 5 * 60

_FACTOR_ERROR_FIELDS = [
    "macd_1d", "rsi_1d", "rsi_value_1d",
    "macd_60m", "rsi_60m", "rsi_value_60m",
    "bb_upper", "bb_mid", "bb_lower",
    "per", "pbr", "roe", "revenue", "net_income",
    "short_score", "long_score",
]

_state: dict | None = None
_state_lock = threading.Lock()

_financials_cache: dict[str, dict] = {}
_financials_cache_lock = threading.Lock()

# (code, tf) → 신선도 게이트로 fetch 를 건너뛸 때 돌려줄 마지막 fetch 의 source.
# candles.py 의 _last_source 와 동일 사상(별도 DB 컬럼 없이 프로세스 메모리로 충분).
_last_source: dict[tuple[str, str], str] = {}
_last_source_lock = threading.Lock()

_thread: threading.Thread | None = None
_stop_event = threading.Event()


# ────────────────────────────────────────────
# 시간대 판정
# ────────────────────────────────────────────

def _is_market_hours(now: datetime) -> bool:
    # 평일·시간뿐 아니라 KRX 휴장일(설/추석·대체공휴일·노동절 등)도 인지한다.
    import market_calendar

    return market_calendar.is_trading_day(now) and _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


def _cycle_interval_seconds() -> int:
    now = datetime.now(ZoneInfo(TIMEZONE))
    return COLLECTOR_INTERVAL_MARKET if _is_market_hours(now) else COLLECTOR_INTERVAL_IDLE


# ────────────────────────────────────────────
# 변환 유틸(캔들 df → 저장소 items) — candles.py 와 동일 규칙을 이 모듈 전용으로 재구현.
# (private 함수를 모듈 경계 넘어 재사용하기보다, 짧은 변환 로직은 로컬에 둔다.)
# ────────────────────────────────────────────

def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if f != f else f  # NaN != NaN
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _daily_date_to_epoch(date_str) -> int | None:
    """'YYYYMMDD' 문자열을 KST 자정 기준 Unix epoch(초)로 변환. 파싱 실패 시 None."""
    try:
        dt = datetime.strptime(str(date_str)[:8], "%Y%m%d").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _minute_ts_to_epoch(ts) -> int | None:
    """tz-aware pandas Timestamp → Unix epoch(초). naive면 서버 기준 TIMEZONE으로 간주."""
    try:
        if ts.tzinfo is None:
            ts = ts.tz_localize(ZoneInfo(TIMEZONE))
        return int(ts.timestamp())
    except (ValueError, TypeError, AttributeError):
        return None


def _df_to_candle_items_daily(df: pd.DataFrame) -> list[dict]:
    items = []
    for _, row in df.iterrows():
        t = _daily_date_to_epoch(row.get("date"))
        if t is None:
            continue
        items.append({
            "t": t,
            "open": _safe_float(row.get("open")),
            "high": _safe_float(row.get("high")),
            "low": _safe_float(row.get("low")),
            "close": _safe_float(row.get("close")),
            "volume": _safe_int(row.get("volume")),
        })
    return items


def _df_to_candle_items_minute(df: pd.DataFrame) -> list[dict]:
    items = []
    for ts, row in df.iterrows():
        t = _minute_ts_to_epoch(ts)
        if t is None:
            continue
        items.append({
            "t": t,
            "open": _safe_float(row.get("open")),
            "high": _safe_float(row.get("high")),
            "low": _safe_float(row.get("low")),
            "close": _safe_float(row.get("close")),
            "volume": _safe_int(row.get("volume")),
        })
    return items


def _price_change(df: pd.DataFrame) -> dict:
    """df(오름차순, close 컬럼 필수) 마지막 2개 종가로 전일 대비 등락폭·등락률 계산."""
    if df is None or len(df) < 2:
        return {"change": None, "change_pct": None}
    prev_close = _safe_float(df.iloc[-2]["close"])
    curr_close = _safe_float(df.iloc[-1]["close"])
    if prev_close is None or curr_close is None or prev_close == 0:
        return {"change": None, "change_pct": None}
    return {
        "change": round(curr_close - prev_close, 2),
        "change_pct": round((curr_close - prev_close) / prev_close * 100, 2),
    }


# ────────────────────────────────────────────
# 재무데이터 6시간 캐시
# ────────────────────────────────────────────

_EMPTY_FINANCIALS = {"per": None, "pbr": None, "roe": None, "revenue": None, "net_income": None}


def _get_financials_cached(code: str, token: str | None) -> dict:
    now = time.monotonic()
    with _financials_cache_lock:
        cached = _financials_cache.get(code)
        if cached is not None and (now - cached["cached_at"]) < cached["ttl"]:
            return cached["data"]

    if token is None:
        return dict(_EMPTY_FINANCIALS)

    try:
        data = crawler.fetch_kis_financials(code, token)
    except Exception as e:
        logger.warning(f"[collector] 재무데이터 수집 실패 ({code}): {e}")
        data = dict(_EMPTY_FINANCIALS)

    ttl = _FINANCIALS_TTL_SECONDS + random.uniform(
        -_FINANCIALS_TTL_JITTER_SECONDS, _FINANCIALS_TTL_JITTER_SECONDS
    )
    with _financials_cache_lock:
        _financials_cache[code] = {"data": data, "cached_at": now, "ttl": ttl}
    return data


# ────────────────────────────────────────────
# 종목별 수집(서버 전용 조립 — crawler.fetch_stock_price 미사용)
# ────────────────────────────────────────────

def _error_item(code: str, name: str, message: str) -> dict:
    return {
        "code": code, "name": name,
        "close": None, "change": None, "change_pct": None,
        "short_view": None, "long_view": None,
        "source": None, "source_60m": None,
        "error": message,
        **{key: None for key in _FACTOR_ERROR_FIELDS},
    }


def _fetch_daily(code: str, token: str | None) -> tuple[pd.DataFrame | None, str | None]:
    df = None
    source = None

    if token is not None:
        try:
            df = crawler.fetch_kis_ohlcv(code, token, period="D", lookback_days=150)
        except Exception as e:
            logger.warning(f"[collector] KIS 일봉 수집 예외 ({code}): {e}")
            df = None
        # 호출 간격은 crawler 안에서 kis_auth.kis_throttle() 이 전역으로 보장한다
        # (예전에는 여기서 다시 sleep 해 지연이 이중 적용됐다 — 워커 4개 × 종목 수만큼
        #  사이클이 불필요하게 길어졌다).
        if df is not None and not df.empty:
            source = "kis"

    if df is None or df.empty:
        logger.warning(f"[collector] ⚠ KIS 일봉 실패, yfinance 폴백: {code}")
        try:
            df = crawler.fetch_yf_ohlcv(code, interval="1d", period="2y")
        except Exception as e:
            logger.warning(f"[collector] yfinance 일봉 폴백 실패 ({code}): {e}")
            df = None
        if df is not None and not df.empty:
            source = "yfinance"

    return df, source


def _remembered_source(code: str, tf: str) -> str:
    with _last_source_lock:
        return _last_source.get((code, tf), "store")


def _remember_source(code: str, tf: str, source: str | None) -> None:
    if source is None:
        return
    with _last_source_lock:
        _last_source[(code, tf)] = source


def _get_daily_df(code: str, token: str | None) -> tuple[pd.DataFrame | None, str | None]:
    """일봉 신선도 게이트(600초). 신선하면 저장소에서 바로 서빙(외부 fetch 생략),
    stale/없으면 기존과 동일하게 fetch → upsert. fetch 실패 시 동작은 기존과 동일
    (None 반환 → 호출부에서 error item 처리, 스코프 확대 없음).
    """
    age = db.get_candles_age_seconds(code, "1d")
    if age is not None and age < _DAILY_FRESH_SECONDS:
        stored = db.get_candles_store(code, "1d", 100)
        if stored:
            return pd.DataFrame(stored), _remembered_source(code, "1d")

    daily_df, source = _fetch_daily(code, token)
    if daily_df is None or daily_df.empty:
        return None, None

    daily_items = _df_to_candle_items_daily(daily_df)
    if daily_items:
        db.upsert_candles(code, "1d", daily_items)
    _remember_source(code, "1d", source)
    stored = db.get_candles_store(code, "1d", 100)
    return (pd.DataFrame(stored) if stored else daily_df), source


def _fetch_60m_from_kis(code: str, token: str | None) -> pd.DataFrame | None:
    """KIS 1분봉(FHKST03010230) → 60분봉 리샘플. 비활성·자격증명 없음·실패 시 None.

    단기 판정이 yfinance 하나에만 매달려 있던 문제(야후 지연·결측·429 → 단기 판정 소실)를
    풀기 위한 1차 경로다. 호출량이 커서 기본 비활성이다(config.KIS_MINUTE_ENABLED 주석 참고).
    """
    if not KIS_MINUTE_ENABLED or token is None:
        return None
    try:
        minutes = crawler.fetch_kis_minute_ohlcv(code, token, KIS_MINUTE_BACKFILL_DAYS)
        if minutes is None or minutes.empty:
            return None
        return crawler.resample_minutes_to_60m(minutes)
    except Exception as e:
        logger.warning(f"[collector] KIS 60분봉 수집 실패 ({code}) — yfinance 폴백: {e}")
        return None


def _get_60m_df(code: str, token: str | None = None) -> tuple[pd.DataFrame | None, str | None]:
    """60분봉 신선도 게이트(5분). 신선하면 저장소에서 바로 서빙(외부 fetch 생략),
    stale/없으면 KIS 분봉 1차 → yfinance 폴백으로 재수집. fetch 실패 시 (None, None)
    → 호출부에서 macd_60m 등 None 유지(반환 규약 불변).

    60분봉은 시간당 1회 갱신이면 충분한 데이터라 분봉 일반 기준(60초)보다 여유 있는
    임계치를 둔다.
    """
    age = db.get_candles_age_seconds(code, "60m")
    if age is not None and age < _60M_FRESH_SECONDS:
        stored = db.get_candles_store(code, "60m", 150)
        if stored:
            return pd.DataFrame(stored), _remembered_source(code, "60m")

    source = "yfinance"
    df60 = _fetch_60m_from_kis(code, token)
    if df60 is not None and not df60.empty:
        source = "kis"
    else:
        try:
            df60 = crawler.fetch_yf_ohlcv(code, interval="60m", period="6mo")
        except Exception as e:
            logger.warning(f"[collector] 60분봉 수집 실패 ({code}): {e}")
            df60 = None

    if df60 is None or df60.empty:
        return None, None

    items60 = _df_to_candle_items_minute(df60)
    if items60:
        db.upsert_candles(code, "60m", items60)
    _remember_source(code, "60m", source)
    stored = db.get_candles_store(code, "60m", 150)
    return (pd.DataFrame(stored) if stored else df60), source


def _collect_one(item: dict, token: str | None) -> dict:
    code = item["code"]
    name = item["name"]

    # ① 일봉(신선도 게이트 — 600초 이내면 저장소에서 바로 서빙, 외부 fetch 생략)
    daily_store_df, source = _get_daily_df(code, token)
    if daily_store_df is None or daily_store_df.empty:
        return _error_item(code, name, f"일봉 수집 실패: {code}")

    close = _safe_float(daily_store_df.iloc[-1]["close"]) if not daily_store_df.empty else None
    change_data = _price_change(daily_store_df)

    try:
        macd_1d = indicators.macd_cross_signal(daily_store_df)
        rsi_1d = indicators.rsi_zone_signal(daily_store_df)
        rsi_value_1d = indicators.rsi_latest_value(daily_store_df)
        bb = indicators.bollinger(daily_store_df)
        bb_upper, bb_mid, bb_lower = bb.get("bb_upper"), bb.get("bb_mid"), bb.get("bb_lower")
    except Exception as e:
        logger.warning(f"[collector] 1일봉 지표 계산 실패 ({code}): {e}")
        macd_1d = rsi_1d = None
        rsi_value_1d = None
        bb_upper = bb_mid = bb_lower = None

    # ② 60분봉(신선도 게이트 — 5분 이내면 저장소에서 바로 서빙, 외부 fetch 생략)
    store60_df, source_60m = _get_60m_df(code, token)
    macd_60m = rsi_60m = None
    rsi_value_60m = None
    if store60_df is not None and not store60_df.empty:
        try:
            macd_60m = indicators.macd_cross_signal(store60_df)
            rsi_60m = indicators.rsi_zone_signal(store60_df)
            rsi_value_60m = indicators.rsi_latest_value(store60_df)
        except Exception as e:
            logger.warning(f"[collector] 60분봉 지표 계산 실패 ({code}): {e}")
            macd_60m = rsi_60m = None
            rsi_value_60m = None

    # ③ 재무(6시간 캐시)
    financials = _get_financials_cached(code, token)

    # ④ views/scores
    view_data = {
        "short_view": indicators.short_term_view(macd_60m, rsi_60m),
        "long_view": indicators.long_term_view(
            macd_1d, rsi_1d, financials["per"], financials["pbr"], financials["roe"]
        ),
        "short_score": indicators.short_term_score(macd_60m, rsi_60m),
        "long_score": indicators.long_term_score(
            macd_1d, rsi_1d, financials["per"], financials["pbr"], financials["roe"]
        ),
    }

    return {
        "code": code, "name": name,
        "close": close,
        **change_data,
        "macd_1d": macd_1d, "rsi_1d": rsi_1d, "rsi_value_1d": rsi_value_1d,
        "macd_60m": macd_60m, "rsi_60m": rsi_60m, "rsi_value_60m": rsi_value_60m,
        "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
        **financials,
        **view_data,
        "source": source, "source_60m": source_60m,
        "error": None,
    }


# ────────────────────────────────────────────
# 사이클 · 루프
# ────────────────────────────────────────────

# KIS 토큰 발급 연속 실패 경보 — 앱키 만료(발급 1년)·폐기가 "조용한 yfinance 강등"으로
# 지나가는 문제의 능동 통지. 화면 배지(SourceBadge)와 /api/health 의 kis 필드는 수동
# 확인 수단이고, 이건 사용자가 안 보고 있어도 알림 채널로 1회 알려주는 마지막 그물이다.
# _run_cycle 은 단일 루프 스레드에서만 돌므로 전역 카운터에 락이 필요 없다.
_KIS_FAIL_ALERT_THRESHOLD = 3
_KIS_FAIL_ALERT_COOLDOWN_SECONDS = 6 * 3600
_kis_fail_streak = 0
_kis_fail_alerted_at: float | None = None  # time.monotonic()


def _note_kis_token_result(ok: bool) -> None:
    """사이클의 토큰 발급 성패를 기록하고, 연속 실패가 임계치에 닿으면 알림 채널
    (Discord/Slack — 켜져 있는 것만)로 시스템 경보를 보낸다. 쿨다운(6시간) 안에는
    재발송하지 않고, 성공이 한 번이라도 나오면 스트릭이 리셋된다. 발송 실패는
    로그만 남긴다(경보 경로가 수집 사이클을 죽이면 안 된다)."""
    global _kis_fail_streak, _kis_fail_alerted_at

    if ok:
        _kis_fail_streak = 0
        return

    _kis_fail_streak += 1
    if _kis_fail_streak < _KIS_FAIL_ALERT_THRESHOLD:
        return

    now = time.monotonic()
    if _kis_fail_alerted_at is not None and (now - _kis_fail_alerted_at) < _KIS_FAIL_ALERT_COOLDOWN_SECONDS:
        return
    _kis_fail_alerted_at = now

    text = (
        f"⚠️ MyStockBot: KIS 토큰 발급이 {_kis_fail_streak}사이클 연속 실패했습니다.\n"
        "전 종목이 yfinance 지연 데이터로 강등된 상태입니다. "
        "앱키 만료(발급 후 1년)·폐기 여부를 확인하세요 — KIS 개발자센터에서 재발급 후 "
        ".env 의 KIS_APP_KEY/KIS_APP_SECRET 교체, 컨테이너 재시작."
    )
    logger.error("[collector] ★ KIS 토큰 연속 %d회 실패 — 시스템 경보 발송 시도", _kis_fail_streak)
    try:
        import alert_channels

        if alert_channels.discord_enabled():
            alert_channels.send_discord(text)
        if alert_channels.slack_enabled():
            alert_channels.send_slack(text)
    except Exception as e:
        logger.warning(f"[collector] 시스템 경보 발송 실패(로그로만 남김): {e}")


def _run_cycle() -> None:
    global _state

    stock_list = db.load_watchlist()
    if not stock_list:
        now = datetime.now(ZoneInfo(TIMEZONE))
        with _state_lock:
            _state = {"generated_at": now.isoformat(), "items": []}
        logger.info("[collector] watchlist 비어있음 — 수집 건너뜀")
        return

    try:
        token = kis_auth.get_token()
    except Exception as e:
        logger.warning(f"[collector] KIS 토큰 발급 실패 — 이번 사이클은 전 종목 yfinance 폴백 경로로 진행: {e}")
        token = None
    _note_kis_token_result(token is not None)

    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_item = {
            executor.submit(_collect_one, stock, token): stock for stock in stock_list
        }
        for future in as_completed(future_to_item):
            stock = future_to_item[future]
            try:
                items.append(future.result())
            except Exception as e:
                logger.warning(f"[collector] 종목 수집 예외 ({stock.get('code')}): {e}")
                items.append(_error_item(stock.get("code"), stock.get("name"), f"수집 예외: {e}"))

    now = datetime.now(ZoneInfo(TIMEZONE))
    with _state_lock:
        _state = {"generated_at": now.isoformat(), "items": items}

    # 판정 전환 알림 — **반드시 락 밖에서.**
    # _state_lock 은 이벤트 루프 스레드가 직접 잡는다(routers/snapshot.py 의 async 핸들러가
    # to_thread 없이 snapshot_cache → collector.get_state() 를 호출한다). 락을 쥔 채
    # SMTP·HTTP 를 하면 서버 전체가 그 시간만큼 응답을 멈춘다.
    # 이 경로는 KIS 를 다시 부르지 않는다 — kis_auth.kis_throttle() 이 전역 락을 잡고
    # 0.5초 sleep 하므로 알림이 수집 사이클을 늘리게 된다. 스냅샷 값만 쓴다.
    try:
        alerts.process_cycle(items, now)
    except Exception as e:
        logger.warning(f"[collector] 판정 전환 알림 처리 실패: {e}")

    success = sum(1 for it in items if it.get("error") is None)
    failed = len(items) - success
    # 정상 사이클은 info, 실패가 섞인 사이클만 warning — 로그 레벨로 걸러 볼 수 있게.
    log = logger.warning if failed else logger.info
    log(f"[collector] 사이클 완료: 성공 {success}건 실패 {failed}건 (전체 {len(items)}건)")


def _loop() -> None:
    logger.info("[collector] 수집 루프 시작")
    try:
        _run_cycle()  # 부팅 직후 즉시 1회
    except Exception as e:
        logger.warning(f"[collector] 부팅 직후 수집 사이클 실패: {e}")

    while not _stop_event.is_set():
        interval = _cycle_interval_seconds()
        if _stop_event.wait(interval):
            break
        try:
            _run_cycle()
        except Exception as e:
            logger.warning(f"[collector] 수집 사이클 실패: {e}")

    logger.info("[collector] 수집 루프 종료")


def start() -> None:
    global _thread
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="collector-loop")
    _thread.start()


def stop() -> None:
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=5)


def get_state() -> dict | None:
    with _state_lock:
        return _state
