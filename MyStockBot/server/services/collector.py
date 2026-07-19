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
    KIS_RATE_LIMIT_DELAY,
    SIXTY_MIN_BOOTSTRAP_RETRY_COOLDOWN_SECONDS,
    TIMEZONE,
)

# 60분봉 리샘플 유틸(resample_items)만 재사용한다(candles.py 소유 로직 — 짧은 변환
# 함수까지 끌어오기보다 이 유틸 하나만 공유해 중복을 줄인다).
from . import candles

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
    "pullback_status", "pullback_reason", "pullback_trend_up",
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
# 관심종목 추가 등 사용자 액션 직후 다음 수집 사이클을 즉시 앞당기기 위한 트리거.
# set()은 어느 스레드(예: FastAPI 요청 핸들러)에서든 호출 가능하지만, 실제 사이클 실행은
# 단일 루프 스레드(_loop)에서만 일어나므로 경합 없음 — _loop 가 폴링 후 clear 한다.
_trigger_event = threading.Event()

# 신규 종목 60분봉 초기 적재(_bootstrap_60m_if_needed) 재시도 쿨다운 — _financials_cache
# 와 동일한 in-memory 쿨다운 패턴(코드별 마지막 시도 시각만 기록).
_60m_bootstrap_cooldown: dict[str, float] = {}
_60m_bootstrap_cooldown_lock = threading.Lock()


# ────────────────────────────────────────────
# 시간대 판정
# ────────────────────────────────────────────

def _is_market_hours(now: datetime) -> bool:
    return now.weekday() < 5 and _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


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


def _kis_minute_epoch(date_str) -> int | None:
    """'YYYYMMDDHHMM' 문자열(KST, KIS 당일분봉)을 Unix epoch(초)로 변환. 파싱 실패 시 None.
    candles.py _kis_minute_epoch 와 동일 규칙(짧은 변환 로직이라 모듈 경계 넘어 재사용하기
    보다 로컬에 둔다 — 이 파일 상단 주석과 동일 관례)."""
    try:
        dt = datetime.strptime(str(date_str)[:12], "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _df_to_candle_items_minute_kis(df: pd.DataFrame) -> list[dict]:
    """crawler.fetch_kis_minutes 결과 전용 변환. 이 df는 (yfinance 분봉과 달리) 의미 있는
    tz-aware 인덱스가 없고 정수 RangeIndex이므로, 'date'='YYYYMMDDHHMM' 문자열을 직접
    KST로 파싱한다."""
    items = []
    for _, row in df.iterrows():
        t = _kis_minute_epoch(row.get("date"))
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
        print(f"[collector] 재무데이터 수집 실패 ({code}): {e}")
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
            print(f"[collector] KIS 일봉 수집 예외 ({code}): {e}")
            df = None
        time.sleep(KIS_RATE_LIMIT_DELAY)
        if df is not None and not df.empty:
            source = "kis"

    if df is None or df.empty:
        print(f"[collector] ⚠ KIS 일봉 실패, yfinance 폴백: {code}")
        try:
            df = crawler.fetch_yf_ohlcv(code, interval="1d", period="2y")
        except Exception as e:
            print(f"[collector] yfinance 일봉 폴백 실패 ({code}): {e}")
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


def _fetch_60m_items(code: str, token: str | None) -> tuple[list[dict], str | None]:
    """60분봉 소스: KIS 당일분봉(1분) 리샘플 우선 → 실패/빈 데이터(장전·휴장·소형주
    정상거래무 등)면 yfinance 로 시끄럽게(경고 로그) 폴백한다. 소형주(예 010170)도
    KIS 당일분봉으로 60m 이 채워져 단기 판정이 나오게 하는 것이 목적.

    token 은 _run_cycle 에서 이미 발급받은 사이클 공용 토큰을 그대로 받는다(사이클마다
    KIS 토큰을 중복 발급하지 않기 위함 — _get_daily_df 와 동일 관례).
    """
    if token is not None:
        try:
            df1 = crawler.fetch_kis_minutes(code, token)
        except Exception as e:
            print(f"[collector] ⚠ KIS 당일분봉 수집 예외({code}) — yfinance 폴백: {e}")
            df1 = None

        if df1 is not None and not df1.empty:
            one_min_items = _df_to_candle_items_minute_kis(df1)
            if one_min_items:
                items60 = candles.resample_items(one_min_items, 60)
                if items60:
                    return items60, "kis"

        print(f"[collector] ⚠ KIS 60분봉(당일분봉 리샘플) 수집 실패/데이터없음 — yfinance 폴백: {code}")
    else:
        print(f"[collector] ⚠ KIS 토큰 미발급 — 60분봉 yfinance 폴백: {code}")
    try:
        df60 = crawler.fetch_yf_ohlcv(code, interval="60m", period="6mo")
    except Exception as e:
        print(f"[collector] 60분봉 yfinance 폴백 실패 ({code}): {e}")
        df60 = None

    if df60 is None or df60.empty:
        return [], None

    return _df_to_candle_items_minute(df60), "yfinance"


def _bootstrap_60m_if_needed(code: str) -> None:
    """신규 관심종목은 60분봉 저장소가 비어 있어 MACD/RSI 계산 최소 봉수
    (indicators._MIN_BARS_MACD)를 채우기 전까지 단기판정이 계속 '데이터부족'이 된다.
    저장소 봉수가 부족하면 yfinance 6개월치를 1회 적재해 초기 공백을 메운다(그 뒤로는
    _get_60m_df 의 KIS 우선 수집이 정상적으로 이어서 쌓는다).

    이는 KIS 우선 원칙을 깨는 예외가 아니라 신규 종목의 초기 적재 공백을 메우는 1회성
    부트스트랩이다(로그 문구를 기존 "yfinance 폴백" 경고와 구분해 "60m 초기 적재"로 남긴다).
    실패 시 조용히 쿨다운만 기록하고 현행 흐름(느린 자연 적재)을 유지한다 — 스코프 확대 없음.
    """
    stored_count = len(db.get_candles_store(code, "60m", 150))
    if stored_count >= indicators._MIN_BARS_MACD:
        return

    now = time.monotonic()
    with _60m_bootstrap_cooldown_lock:
        last_attempt = _60m_bootstrap_cooldown.get(code)
        if last_attempt is not None and (now - last_attempt) < SIXTY_MIN_BOOTSTRAP_RETRY_COOLDOWN_SECONDS:
            return
        _60m_bootstrap_cooldown[code] = now

    try:
        df60 = crawler.fetch_yf_ohlcv(code, interval="60m", period="6mo")
    except Exception as e:
        print(f"[collector] 60m 초기 적재 실패 ({code}): {e}")
        return

    if df60 is None or df60.empty:
        print(f"[collector] 60m 초기 적재: yfinance 데이터 없음 ({code})")
        return

    items60 = _df_to_candle_items_minute(df60)
    if not items60:
        return

    db.upsert_candles(code, "60m", items60)
    print(f"[collector] 60m 초기 적재 완료 ({code}): {len(items60)}건")


def _get_60m_df(code: str, token: str | None) -> tuple[pd.DataFrame | None, str | None]:
    """60분봉 신선도 게이트(5분). 신선하면 저장소에서 바로 서빙(외부 fetch 생략),
    stale/없으면 KIS 당일분봉(1분) 리샘플 우선 → yfinance 폴백으로 재수집. fetch 실패
    시 동작은 기존과 동일(None 반환 → 호출부에서 macd_60m 등 None 유지, 스코프 확대 없음).

    60분봉은 시간당 1회 갱신이면 충분한 데이터라 분봉 일반 기준(60초)보다 여유 있는
    임계치를 둔다. 신규 종목(저장소 봉수 부족)은 먼저 _bootstrap_60m_if_needed 로
    초기 적재를 시도한 뒤 기존 신선도 게이트 로직을 그대로 이어간다.
    """
    _bootstrap_60m_if_needed(code)

    age = db.get_candles_age_seconds(code, "60m")
    if age is not None and age < _60M_FRESH_SECONDS:
        stored = db.get_candles_store(code, "60m", 150)
        if stored:
            return pd.DataFrame(stored), _remembered_source(code, "60m")

    items60, source = _fetch_60m_items(code, token)
    if not items60:
        return None, None

    db.upsert_candles(code, "60m", items60)
    _remember_source(code, "60m", source)
    stored = db.get_candles_store(code, "60m", 150)
    return (pd.DataFrame(stored) if stored else pd.DataFrame(items60)), source


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
        print(f"[collector] 1일봉 지표 계산 실패 ({code}): {e}")
        macd_1d = rsi_1d = None
        rsi_value_1d = None
        bb_upper = bb_mid = bb_lower = None

    # ①-2 눌림목(pullback) 판정 — 기존 일봉 지표(MACD/RSI/BB) try 블록과 분리된 별도
    # try/except. 이 계산이 실패해도 위 지표들에는 영향이 없어야 한다(스코프 격리).
    try:
        pullback = indicators.pullback_signal(daily_store_df)
        pullback_status = pullback.get("status")
        pullback_reason = pullback.get("reason")
        pullback_trend_up = pullback.get("trend_up")
    except Exception as e:
        print(f"[collector] 눌림목 판정 실패 ({code}): {e}")
        pullback_status = pullback_reason = pullback_trend_up = None

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
            print(f"[collector] 60분봉 지표 계산 실패 ({code}): {e}")
            macd_60m = rsi_60m = None
            rsi_value_60m = None

    # ③ 재무(6시간 캐시)
    financials = _get_financials_cached(code, token)

    # ④ views/scores — 장기(1d) 관점은 눌림목 추세 필터(trend_up) 반영: 추세장에서는
    # RSI 과매수 감점을 무효화한다(indicators._rsi_score 참조). 실패 시 pullback_trend_up
    # 이 None 이므로 bool(None)=False 로 안전 폴백(기존 동작과 동일).
    trend_up = bool(pullback_trend_up)
    view_data = {
        "short_view": indicators.short_term_view(macd_60m, rsi_60m),
        "long_view": indicators.long_term_view(
            macd_1d, rsi_1d, financials["per"], financials["pbr"], financials["roe"], trend_up=trend_up
        ),
        "short_score": indicators.short_term_score(macd_60m, rsi_60m),
        "long_score": indicators.long_term_score(
            macd_1d, rsi_1d, financials["per"], financials["pbr"], financials["roe"], trend_up=trend_up
        ),
    }

    return {
        "code": code, "name": name,
        "close": close,
        **change_data,
        "macd_1d": macd_1d, "rsi_1d": rsi_1d, "rsi_value_1d": rsi_value_1d,
        "macd_60m": macd_60m, "rsi_60m": rsi_60m, "rsi_value_60m": rsi_value_60m,
        "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
        "pullback_status": pullback_status,
        "pullback_reason": pullback_reason,
        "pullback_trend_up": pullback_trend_up,
        **financials,
        **view_data,
        "source": source, "source_60m": source_60m,
        "error": None,
    }


# ────────────────────────────────────────────
# 사이클 · 루프
# ────────────────────────────────────────────

def _run_cycle() -> None:
    global _state

    stock_list = db.load_watchlist()
    if not stock_list:
        now = datetime.now(ZoneInfo(TIMEZONE))
        with _state_lock:
            _state = {"generated_at": now.isoformat(), "items": []}
        print("[collector] watchlist 비어있음 — 수집 건너뜀")
        return

    try:
        token = kis_auth.get_token()
    except Exception as e:
        print(f"[collector] KIS 토큰 발급 실패 — 이번 사이클은 전 종목 yfinance 폴백 경로로 진행: {e}")
        token = None

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
                print(f"[collector] 종목 수집 예외 ({stock.get('code')}): {e}")
                items.append(_error_item(stock.get("code"), stock.get("name"), f"수집 예외: {e}"))

    now = datetime.now(ZoneInfo(TIMEZONE))
    with _state_lock:
        _state = {"generated_at": now.isoformat(), "items": items}

    success = sum(1 for it in items if it.get("error") is None)
    print(f"[collector] 사이클 완료: 성공 {success}건 실패 {len(items) - success}건 (전체 {len(items)}건)")


def _interruptible_wait(interval: int) -> bool:
    """interval 초를 1초 단위로 쪼개 기다리며 _stop_event/_trigger_event 를 폴링한다.

    stop 시 True(루프 종료) 반환. trigger 시 이벤트를 clear 하고 False(즉시 사이클 재개)
    반환. 정상 만료 시에도 False 반환. 단일 루프 스레드에서만 호출되므로 경합 없음.
    """
    elapsed = 0
    while elapsed < interval:
        if _stop_event.wait(1):
            return True
        if _trigger_event.is_set():
            _trigger_event.clear()
            return False
        elapsed += 1
    return False


def _loop() -> None:
    print("[collector] 수집 루프 시작")
    try:
        _run_cycle()  # 부팅 직후 즉시 1회
    except Exception as e:
        print(f"[collector] 부팅 직후 수집 사이클 실패: {e}")

    while not _stop_event.is_set():
        interval = _cycle_interval_seconds()
        if _interruptible_wait(interval):
            break
        try:
            _run_cycle()
        except Exception as e:
            print(f"[collector] 수집 사이클 실패: {e}")

    print("[collector] 수집 루프 종료")


def trigger_immediate_cycle() -> None:
    """다음 수집 사이클을 즉시 앞당긴다(대기 인터벌 중단). 관심종목 신규 추가 직후처럼
    사용자가 결과를 빨리 보고 싶어하는 시점에 호출한다. 이벤트 set만 하고 즉시 반환하며,
    실제 수집은 루프 스레드가 다음 폴링에서 수행한다."""
    _trigger_event.set()


def start() -> None:
    global _thread
    _stop_event.clear()
    _trigger_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="collector-loop")
    _thread.start()


def stop() -> None:
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=5)


def get_state() -> dict | None:
    with _state_lock:
        return _state
