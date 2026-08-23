"""멀티 타임프레임 캔들 서비스.

GET /api/stocks/{code}/candles 라우트의 비즈니스 로직.
- 소스 라우팅:
  - 일봉+(1d/1w/1M)는 KIS 기간별시세 페이지네이션(fetch_kis_ohlcv_paged — 호출당 100건
    상한을 날짜구간 역행 반복호출로 우회) 우선, 실패 시 yfinance 폴백. 1y 는 기존과
    동일하게 단일 호출(fetch_kis_ohlcv) 유지, 폴백 없음.
  - 분봉(1m/5m/15m/30m/60m)은 yfinance 직접 조회. 120m/240m 은 get_candles(...,"60m",...)
    재귀 호출 결과를 clock-aligned 리샘플(60m 게이트·쿨다운을 그대로 물려받아 60m 이
    깊어지면 자동으로 함께 깊어진다).
- epoch 변환: 일봉+ 는 KST 자정 기준, 분봉은 원본 tz-aware 타임스탬프의 실제 시각 기준.
- count 상한: 1d/1w/60m/120m/240m 는 최대 1000(과거 깊이 허용 — 1d/1w 는 페이지네이션,
  60m 계열은 yfinance 730d 딥 수집으로 확보), 그 외(1m/5m/15m/30m/1M/1y)는 300 유지
  (원천 자체가 얕아 상한을 올려도 의미 없음).
- 영속 저장소(db.candles) read-through: 신선(분봉 60초·일봉+ 600초) 이내면 저장소에서
  바로 서빙, stale/없음이면 fetch → upsert_candles → 저장소에서 재조회해 서빙(기존
  이력과 병합된 채로 나간다 — collector.py가 채워둔 데이터와도 자연히 합쳐짐).
  fetch 실패 시 저장소에 남은 값(낡아도)을 서빙, 그마저 없으면 빈 items(기존 계약).
- 깊이 게이트: 저장소가 신선해도 요청 개수보다 얕으면(과거가 아직 안 쌓임) 딥 수집을
  시도한다 — 신선도만 보면 얕은 100개가 고착됨(실측으로 발견된 버그). 원천 자체가 얕은
  종목(신규상장 등)의 무한 재수집은 두 겹으로 방어한다:
    ① (code, tf) 쿨다운(_DEEP_FETCH_COOLDOWN_SECONDS)
    ② 원천 고갈 바닥(_history_floor) — 딥 수집이 요청을 못 채우고 끝나면 그때의 최저
       t 를 기억해, 그 아래를 요구하는 요청은 외부 호출 없이 저장소만으로 응답한다.
- before 커서: get_candles(..., before=epoch) 는 t < before 구간만 돌려준다(차트 왼쪽
  스크롤 무한 로딩용). 저장소가 부족하면 1d/1w/1M 에 한해 KIS 페이지네이션을 before
  이전 구간부터 역행 수행해 채운다. 과거 데이터는 불변이므로 신선도 게이트는 없다.
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

import crawler
import db
import kis_auth
from config import TIMEZONE

logger = logging.getLogger(__name__)

# tf → (KIS FID_PERIOD_DIV_CODE, KIS 기간별시세 조회 lookback 일수)
# lookback 은 1y(단일 호출 경로)에서만 쓰인다 — 1d/1w/1M 은 페이지네이션이 target_count
# 기준으로 알아서 과거로 내려간다.
_KIS_PERIOD_MAP = {
    "1d": ("D", 150),
    "1w": ("W", 365 * 2),
    "1M": ("M", 365 * 8),
    "1y": ("Y", 365 * 30),
}

# before 커서·페이지네이션 지원 tf → KIS period 코드
_PAGED_TFS = {"1d": "D", "1w": "W", "1M": "M"}

# KIS 실패 시 yfinance 폴백 (interval, period) — 1y 는 폴백 없음(스펙 명시)
_YF_FALLBACK_MAP = {
    "1d": ("1d", "2y"),
    "1w": ("1wk", "10y"),
    "1M": ("1mo", "max"),
}

# 분봉 tf 중 yfinance에서 직접 조회 가능한 것들 → (interval, period)
# 60m 은 "730d"(yfinance 60분 간격 조회의 하드 한계) — 과거 깊이 확장을 위해 "6mo"에서 상향.
# ("2y"는 yfinance 쪽에서 60분 간격 한계 경계상 거부될 수 있어 "730d" 리터럴을 그대로 쓴다.)
_YF_DIRECT_MAP = {
    "1m": ("1m", "7d"),
    "5m": ("5m", "60d"),
    "15m": ("15m", "60d"),
    "30m": ("30m", "60d"),
    "60m": ("60m", "730d"),
}

# 120m/240m 은 60분봉을 서버에서 다시 리샘플(버킷 크기 = 분 단위,
# resample_items 가 clock-aligned floor 로 그룹핑).
_RESAMPLE_UNIT = {"120m": 120, "240m": 240}

_MINUTE_TFS = {"1m", "5m", "15m", "30m", "60m", "120m", "240m"}
_DAILY_PLUS_TFS = {"1d", "1w", "1M", "1y"}

# 딥 수집(과거 깊이 확장) 게이트 대상 — 저장소가 신선해도 요청보다 얕으면 더 수집한다.
# 1m~30m 은 대상이 아니다(yfinance 원천이 60일 이하라 깊어질 수 없음 — 주기 갱신만).
_DEEP_GATE_TFS = _DAILY_PLUS_TFS | {"60m", "120m", "240m"}

VALID_TFS = _MINUTE_TFS | _DAILY_PLUS_TFS

_MINUTE_FRESH_SECONDS = 60
_DAILY_FRESH_SECONDS = 600

_DEFAULT_COUNT = 150
_MAX_COUNT = 300         # 1m/5m/15m/30m·1M·1y 상한(기존 유지)
_MAX_COUNT_DEEP = 1000   # 1d/1w/60m/120m/240m 전용 상한(과거 깊이 허용)
_DEEP_COUNT_TFS = {"1d", "1w", "60m", "120m", "240m"}

# 저장소가 이미 요청만큼 깊을 때의 최신화(stale 갱신) 목표 봉수 — 페이지네이션 1페이지
# 분량이면 최근 구간 갱신에 충분하다(매 갱신마다 딥 페이지네이션을 반복하지 않기 위함).
_REFRESH_TARGET = 100

# (code, tf) → 이번 서버 세션에서 마지막으로 저장소에 upsert한 fetch의 source("kis"|"yfinance").
# 별도 candles_meta 테이블 없이 과설계를 피하기 위한 인메모리 기록 — 서버 재시작 후
# 저장소가 신선해서 fetch 없이 바로 서빙하는 경우엔 이 기록이 비어 있으므로 "store"로 대체한다.
_last_source: dict[tuple[str, str], str] = {}
_source_lock = threading.Lock()

# 딥 수집 재시도 쿨다운(초) — 원천 자체가 얕은 종목(신규상장 등)이 신선도 게이트를
# 매번 통과할 때마다 외부 호출을 반복하지 않도록 방어.
_DEEP_FETCH_COOLDOWN_SECONDS = 600
_deep_fetch_attempted_at: dict[tuple[str, str], float] = {}
_deep_fetch_lock = threading.Lock()

# (code, tf) → 원천 고갈 바닥 epoch. 딥 수집이 요청을 못 채우고 끝났을 때의 최저 t.
# 이 바닥 이하를 요구하는 요청은 외부 호출 없이 저장소만으로 응답한다(서버 재시작 시
# 리셋 — 재시작당 1회의 재확인 비용만 지불).
_history_floor: dict[tuple[str, str], int] = {}
_floor_lock = threading.Lock()


def _fresh_threshold(tf: str) -> int:
    return _MINUTE_FRESH_SECONDS if tf in _MINUTE_TFS else _DAILY_FRESH_SECONDS


def _max_count_for(tf: str) -> int:
    return _MAX_COUNT_DEEP if tf in _DEEP_COUNT_TFS else _MAX_COUNT


def _remembered_source(code: str, tf: str) -> str:
    with _source_lock:
        return _last_source.get((code, tf), "store")


def _remember_source(code: str, tf: str, source: str | None) -> None:
    if source is None:
        return
    with _source_lock:
        _last_source[(code, tf)] = source


def _deep_fetch_cooldown_ok(code: str, tf: str) -> bool:
    """딥 수집 시도 가능 여부. 쿨다운 내 재시도면 False(그 사이엔 저장소가 얕아도 그대로
    서빙). True 를 돌려줄 때는 시도 시각을 함께 기록한다 — 성공 여부와 무관하게 시도
    자체를 기록해 쿨다운을 재시작한다."""
    now = time.monotonic()
    with _deep_fetch_lock:
        last = _deep_fetch_attempted_at.get((code, tf))
        if last is not None and (now - last) < _DEEP_FETCH_COOLDOWN_SECONDS:
            return False
        _deep_fetch_attempted_at[(code, tf)] = now
        return True


def _get_history_floor(code: str, tf: str) -> int | None:
    with _floor_lock:
        return _history_floor.get((code, tf))


def _set_history_floor(code: str, tf: str, floor_t: int) -> None:
    with _floor_lock:
        prev = _history_floor.get((code, tf))
        # 바닥은 아래로만 내려간다(더 과거가 확인되면 갱신, 위로는 되돌리지 않음).
        if prev is None or floor_t < prev:
            _history_floor[(code, tf)] = floor_t


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        if pd.isna(val):
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


def _kst_midnight_epoch(date_str) -> int | None:
    """'YYYYMMDD' 문자열을 KST 자정 기준 Unix epoch(초)로 변환. 파싱 실패 시 None."""
    try:
        dt = datetime.strptime(str(date_str)[:8], "%Y%m%d").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _minute_epoch(ts) -> int | None:
    """tz-aware pandas Timestamp → Unix epoch(초). naive면 서버 기준 TIMEZONE으로 간주."""
    try:
        if ts.tzinfo is None:
            ts = ts.tz_localize(ZoneInfo(TIMEZONE))
        return int(ts.timestamp())
    except (ValueError, TypeError, AttributeError):
        return None


def _row_to_item(row, t: int) -> dict:
    return {
        "t": t,
        "open": _safe_float(row.get("open")),
        "high": _safe_float(row.get("high")),
        "low": _safe_float(row.get("low")),
        "close": _safe_float(row.get("close")),
        "volume": _safe_int(row.get("volume")),
    }


def _df_to_items_daily(df: pd.DataFrame) -> list[dict]:
    items = []
    for _, row in df.iterrows():
        t = _kst_midnight_epoch(row.get("date"))
        if t is None:
            continue
        items.append(_row_to_item(row, t))
    return items


def _df_to_items_minute(df: pd.DataFrame) -> list[dict]:
    items = []
    for ts, row in df.iterrows():
        t = _minute_epoch(ts)
        if t is None:
            continue
        items.append(_row_to_item(row, t))
    return items


def resample_items(items: list[dict], unit_minutes: int) -> list[dict]:
    """t 오름차순 캔들 items를 unit_minutes 크기의 clock-aligned(절대 시각 기준) 버킷으로
    묶어 상위 tf 캔들로 합성한다.

    버킷 경계는 items 리스트의 첫 항목(=조회창 시작)이 아니라 절대 epoch을
    floor(t / (unit_minutes*60)) * (unit_minutes*60) 로 계산한다. KST epoch 0(1970-01-01
    00:00 UTC)이 정확히 1970-01-01 09:00 KST이고, 지원하는 모든 버킷 크기(120/240분)가
    하루(86400초)를 나누어떨어지므로, 이 floor 연산은 조회창이 어디서 시작하든 항상
    같은 버킷 경계를 만들어낸다.
    (이전에는 조회창 시작 위치 기준 positional 그룹핑이라, 조회창이 밀리면 같은 실제
    구간인데도 재조회 시각마다 버킷 시작 epoch(t)이 달라져 candles PK (code, tf, t)
    REPLACE 가 아니라 매번 새 행으로 쌓이는 오염이 있었다 — 이를 해결한다. 기존 오염
    행은 db.init_db 가 경계 불일치 조건으로 멱등 정리한다.)

    open=버킷 첫 값, high=버킷 최댓값, low=버킷 최솟값, close=버킷 마지막 값, volume=버킷 합.
    unit_minutes<=1 이거나 items 가 비면 입력을 그대로 반환한다.
    """
    if not items or unit_minutes <= 1:
        return items

    bucket_seconds = unit_minutes * 60
    buckets: dict[int, list[dict]] = {}
    order: list[int] = []
    for item in items:
        t = item.get("t")
        if t is None:
            continue
        bucket_t = (t // bucket_seconds) * bucket_seconds
        if bucket_t not in buckets:
            buckets[bucket_t] = []
            order.append(bucket_t)
        buckets[bucket_t].append(item)

    out = []
    for bucket_t in order:
        chunk = buckets[bucket_t]
        highs = [c["high"] for c in chunk if c.get("high") is not None]
        lows = [c["low"] for c in chunk if c.get("low") is not None]
        vols = [c["volume"] for c in chunk if c.get("volume") is not None]
        out.append({
            "t": bucket_t,
            "open": chunk[0].get("open"),
            "high": max(highs) if highs else None,
            "low": min(lows) if lows else None,
            "close": chunk[-1].get("close"),
            "volume": sum(vols) if vols else None,
        })
    return out


def _fetch_daily_plus(code: str, tf: str, target: int) -> tuple[pd.DataFrame | None, str | None]:
    period, lookback_days = _KIS_PERIOD_MAP[tf]

    try:
        token = kis_auth.get_token()
    except Exception as e:
        logger.warning(f"[candles] KIS 토큰 발급 실패({code},{tf}) — yfinance 폴백 경로로 진행: {e}")
        token = None

    if token is not None:
        if tf == "1y":
            # 년봉은 기존과 동일하게 단일 호출 유지(30년 lookback 이면 충분).
            df = crawler.fetch_kis_ohlcv(code, token, period=period, lookback_days=lookback_days)
        else:
            df = crawler.fetch_kis_ohlcv_paged(code, token, period=period, target_count=target)
        if df is not None and not df.empty:
            return df, "kis"

    yf_spec = _YF_FALLBACK_MAP.get(tf)
    if yf_spec is None:
        return None, None  # 1y 는 yfinance 폴백 없음(스펙 명시)

    interval, yf_period = yf_spec
    df = crawler.fetch_yf_ohlcv(code, interval=interval, period=yf_period)
    if df is not None and not df.empty:
        return df, "yfinance"
    return None, None


def _fetch_minute(code: str, tf: str, target: int) -> tuple[list[dict], str | None]:
    if tf in _RESAMPLE_UNIT:
        # 120m/240m 은 자체 라이브 조회 대신 get_candles(...,"60m",...) 재귀 호출로
        # 60m 전용 신선도·깊이 게이트(딥 수집·쿨다운 포함)를 그대로 재사용한다 —
        # 60m 저장소가 깊어지면 120m/240m 도 로직 중복 없이 자동으로 깊어진다.
        unit = _RESAMPLE_UNIT[tf]
        base = get_candles(code, "60m", target * (unit // 60))
        base_items = base.get("items") or []
        if not base_items:
            return [], None
        return resample_items(base_items, unit), base.get("source")

    interval, period = _YF_DIRECT_MAP[tf]
    df = crawler.fetch_yf_ohlcv(code, interval=interval, period=period)
    if df is None or df.empty:
        return [], None
    return _df_to_items_minute(df), "yfinance"


def _fetch(code: str, tf: str, target: int) -> tuple[list[dict], str | None]:
    if tf in _DAILY_PLUS_TFS:
        df, source = _fetch_daily_plus(code, tf, target)
        items = _df_to_items_daily(df) if df is not None and not df.empty else []
        return items, (source if items else None)

    items, source = _fetch_minute(code, tf, target)
    return items, (source if items else None)


def _build_response(
    code: str, tf: str, source: str | None, items: list[dict], count: int,
    fetch_error: bool = False,
) -> dict:
    sliced = items[-count:] if items else []
    return {
        "code": code,
        "tf": tf,
        "source": source if sliced else None,
        "items": sliced,
        # 내부 소비자(dca/backtest)가 "소스 장애"와 "진짜 이력 없음"을 구분하기 위한 신호.
        # CandlesResponse 스키마엔 없는 키라 HTTP 응답에는 노출되지 않는다(response_model 필터).
        "fetch_error": fetch_error,
    }


def _get_candles_before(code: str, tf: str, safe_count: int, before_t: int) -> dict:
    """before 커서 경로 — t < before_t 인 캔들 마지막 safe_count개.

    과거 데이터는 불변이므로 신선도 게이트가 없다. 저장소가 부족하면 1d/1w/1M 에 한해
    KIS 페이지네이션을 before 이전 구간부터 역행 수행해 채우고, 그래도 못 채우면 원천
    고갈로 보고 바닥(_history_floor)을 기록해 다음 요청부터 외부 호출을 생략한다.
    분봉은 어떤 소스도 임의 과거를 소급 조회할 수 없어 저장소만으로 응답한다.
    """
    stored = db.get_candles_store_before(code, tf, safe_count, before_t)
    if len(stored) >= safe_count or tf not in _PAGED_TFS:
        return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

    floor = _get_history_floor(code, tf)
    if floor is not None and before_t <= floor:
        # 이 경계 아래로는 더 없음이 확인됨 — 저장소가 전부다.
        return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

    try:
        token = kis_auth.get_token()
    except Exception as e:
        logger.warning(f"[candles] KIS 토큰 발급 실패({code},{tf},before) — 저장소만으로 응답: {e}")
        token = None

    if token is not None:
        end_dt = datetime.fromtimestamp(before_t, ZoneInfo(TIMEZONE)) - timedelta(days=1)
        df = crawler.fetch_kis_ohlcv_paged(
            code, token, period=_PAGED_TFS[tf], target_count=safe_count, end=end_dt,
        )
        if df is not None and not df.empty:
            # 경계 방어: KIS 가 경계 당일을 포함해 돌려줘도 before 미만만 취한다.
            items = [it for it in _df_to_items_daily(df) if it["t"] < before_t]
            if items:
                db.upsert_candles(code, tf, items)
                _remember_source(code, tf, "kis")
            stored = db.get_candles_store_before(code, tf, safe_count, before_t)
            if len(stored) < safe_count:
                # KIS 가 응답했는데도 못 채움 = 원천 고갈(상장 이전 구간).
                _set_history_floor(code, tf, before_t)
        # df None(요청 실패/빈 응답)은 일시 장애일 수 있어 바닥을 기록하지 않는다 —
        # 다음 스크롤에서 재시도된다(kis_throttle 이 호출 빈도를 이미 묶는다).

    return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)


def get_candles(code: str, tf: str, count: int = _DEFAULT_COUNT, before: int | None = None) -> dict:
    """(code, tf) 캔들 조회. 영속 저장소(db.candles) read-through.

    before 가 주어지면 t < before 구간의 마지막 count개(_get_candles_before 참조).

    그 외에는: 저장소가 신선(분봉 60초·일봉+ 600초 이내)하고 요청만큼 깊으면 fetch 없이
    바로 서빙한다. 신선해도 얕으면(딥 게이트 대상 tf) 쿨다운·원천 고갈 바닥을 거쳐 딥
    수집을 시도한다. stale 이면 최신화 fetch — 저장소가 이미 깊으면 1페이지 분량만
    갱신한다(_REFRESH_TARGET). fetch 실패 시 저장소에 남은 낡은 데이터라도 서빙하고,
    그마저 없으면 items=[]·source=None 인 정상 응답(라우터에서 200 — 기존 계약 그대로).
    """
    safe_count = max(1, min(int(count), _max_count_for(tf)))

    if before is not None:
        return _get_candles_before(code, tf, safe_count, int(before))

    age = db.get_candles_age_seconds(code, tf)
    fresh = age is not None and age < _fresh_threshold(tf)
    stored = db.get_candles_store(code, tf, safe_count)

    deep_needed = tf in _DEEP_GATE_TFS and len(stored) < safe_count
    if deep_needed:
        floor = _get_history_floor(code, tf)
        if floor is not None and stored and stored[0]["t"] <= floor:
            deep_needed = False  # 원천 고갈 확인됨 — 있는 만큼이 전부
        elif not _deep_fetch_cooldown_ok(code, tf):
            deep_needed = False  # 쿨다운 — 이번엔 딥 수집 없이 진행

    if fresh and not deep_needed:
        return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

    # stale 최신화 시 저장소가 이미 깊으면 최근 구간만 갱신한다(딥 페이지네이션 반복 방지).
    target = safe_count if deep_needed else min(safe_count, _REFRESH_TARGET)

    fetch_error = False
    try:
        items, source = _fetch(code, tf, target)
    except Exception as e:
        logger.warning(f"[candles] 수집 실패 ({code}, {tf}): {e}")
        items, source = [], None
        fetch_error = True

    if items:
        db.upsert_candles(code, tf, items)
        _remember_source(code, tf, source)
        stored = db.get_candles_store(code, tf, safe_count)
        if deep_needed and len(stored) < safe_count and stored:
            # 딥 수집이 응답을 받았는데도 요청을 못 채움 = 원천 고갈(상장 이력이 짧음).
            # 최저 t 를 바닥으로 기록해 다음 요청부터 재수집을 생략한다.
            _set_history_floor(code, tf, stored[0]["t"])
        return _build_response(code, tf, source, stored, safe_count)

    # fetch 실패/빈 데이터 — 저장소에 낡은 값이라도 있으면 그거라도 서빙.
    if stored:
        logger.warning(f"[candles] 최신 수집 실패 — 저장소의 낡은 데이터로 서빙 ({code}, {tf})")
        return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

    # 데이터가 아예 없음: fetch 예외였는지(소스 장애) 빈 응답이었는지 구분해 전달.
    return _build_response(code, tf, None, [], safe_count, fetch_error=fetch_error)


def backfill_history(code: str) -> None:
    """관심종목의 일/주/월봉 과거 이력을 저장소에 미리 채운다.

    목적: 온디맨드 딥 수집(페이지네이션 ~10콜, 첫 차트 로딩 수 초)을 사용자가 기다리지
    않게 한다. watchlist 추가 직후(백그라운드 태스크)와 야간 배치(scheduler)에서 호출.
    get_candles 의 깊이 게이트·쿨다운·바닥 기억을 그대로 지나가므로 이미 채워진 종목은
    저렴하게 끝난다. 실패는 로그만 남긴다 — 다음 기회(온디맨드/다음 배치)에 재시도된다.
    """
    for tf, want in (("1d", _MAX_COUNT_DEEP), ("1w", _MAX_COUNT_DEEP), ("1M", _MAX_COUNT)):
        try:
            res = get_candles(code, tf, want)
            logger.info(f"[candles] 백필 {code} {tf}: {len(res.get('items') or [])}건")
        except Exception as e:
            logger.warning(f"[candles] 백필 실패 ({code}, {tf}): {e}")
