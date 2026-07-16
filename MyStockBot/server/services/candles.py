"""멀티 타임프레임 캔들 서비스.

GET /api/stocks/{code}/candles 라우트의 비즈니스 로직.
- 소스 라우팅: 일봉+(1d/1w/1M/1y)는 KIS 기간별시세 우선, 실패 시 yfinance 폴백(1y는 폴백 없음).
  분봉(1m/5m/15m/30m/60m)은 yfinance 직접 조회. 120m/240m은 60분봉을 서버에서 리샘플.
- epoch 변환: 일봉+ 는 KST 자정 기준, 분봉은 원본 tz-aware 타임스탬프의 실제 시각 기준.
- (code, tf) 단위 TTL 인메모리 캐시(분봉 60초·일봉+ 600초).
"""
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import crawler
import kis_auth
from config import TIMEZONE

# tf → (KIS FID_PERIOD_DIV_CODE, KIS 기간별시세 조회 lookback 일수)
_KIS_PERIOD_MAP = {
    "1d": ("D", 150),
    "1w": ("W", 365 * 2),
    "1M": ("M", 365 * 8),
    "1y": ("Y", 365 * 30),
}

# KIS 실패 시 yfinance 폴백 (interval, period) — 1y 는 폴백 없음(스펙 명시)
_YF_FALLBACK_MAP = {
    "1d": ("1d", "2y"),
    "1w": ("1wk", "10y"),
    "1M": ("1mo", "max"),
}

# 분봉 tf 중 yfinance에서 직접 조회 가능한 것들 → (interval, period)
_YF_DIRECT_MAP = {
    "1m": ("1m", "7d"),
    "5m": ("5m", "60d"),
    "15m": ("15m", "60d"),
    "30m": ("30m", "60d"),
    "60m": ("60m", "6mo"),
}

# 120m/240m 은 60분봉 원본을 서버에서 리샘플(연속 n개 봉을 하나로 묶음)
_RESAMPLE_UNIT = {"120m": 2, "240m": 4}

_MINUTE_TFS = {"1m", "5m", "15m", "30m", "60m", "120m", "240m"}
_DAILY_PLUS_TFS = {"1d", "1w", "1M", "1y"}

VALID_TFS = _MINUTE_TFS | _DAILY_PLUS_TFS

_MINUTE_CACHE_TTL_SECONDS = 60
_DAILY_CACHE_TTL_SECONDS = 600

_DEFAULT_COUNT = 150
_MAX_COUNT = 300

# (code, tf) → {"items": [...], "source": str|None, "cached_at": float(monotonic)}
# 스냅샷 캐시(snapshot_cache.py)와 동일하게 단일 락으로 단순화한다 — 개인용 소규모 트래픽 전제.
_cache: dict[tuple[str, str], dict] = {}
_lock = threading.Lock()


def _cache_ttl(tf: str) -> int:
    return _MINUTE_CACHE_TTL_SECONDS if tf in _MINUTE_TFS else _DAILY_CACHE_TTL_SECONDS


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


def _resample(df: pd.DataFrame, unit: int) -> pd.DataFrame:
    """시간 오름차순 df를 연속 unit개 봉 단위로 묶는다(마지막 불완전 버킷도 포함).

    open=버킷 첫 값, high=버킷 최댓값, low=버킷 최솟값, close=버킷 마지막 값, volume=버킷 합.
    인덱스(타임스탬프)는 버킷 첫 행의 것을 유지한다(버킷 시작 시각을 캔들 시각으로 사용).
    """
    if df is None or df.empty:
        return df

    rows = []
    idx = []
    for start in range(0, len(df), unit):
        chunk = df.iloc[start:start + unit]
        if chunk.empty:
            continue
        rows.append({
            "date": chunk.iloc[0]["date"],
            "open": chunk.iloc[0]["open"],
            "high": chunk["high"].max(),
            "low": chunk["low"].min(),
            "close": chunk.iloc[-1]["close"],
            "volume": chunk["volume"].sum(),
        })
        idx.append(chunk.index[0])

    out = pd.DataFrame(rows)
    out.index = idx
    return out


def _fetch_daily_plus(code: str, tf: str) -> tuple[pd.DataFrame | None, str | None]:
    period, lookback_days = _KIS_PERIOD_MAP[tf]

    try:
        token = kis_auth.get_token()
    except Exception as e:
        print(f"[candles] KIS 토큰 발급 실패({code},{tf}) — yfinance 폴백 경로로 진행: {e}")
        token = None

    if token is not None:
        df = crawler.fetch_kis_ohlcv(code, token, period=period, lookback_days=lookback_days)
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


def _fetch_minute(code: str, tf: str) -> tuple[pd.DataFrame | None, str | None]:
    if tf in _RESAMPLE_UNIT:
        base_df = crawler.fetch_yf_ohlcv(code, interval="60m", period="6mo")
        if base_df is None or base_df.empty:
            return None, None
        df = _resample(base_df, _RESAMPLE_UNIT[tf])
        if df is None or df.empty:
            return None, None
        return df, "yfinance"

    interval, period = _YF_DIRECT_MAP[tf]
    df = crawler.fetch_yf_ohlcv(code, interval=interval, period=period)
    if df is None or df.empty:
        return None, None
    return df, "yfinance"


def _fetch(code: str, tf: str) -> tuple[list[dict], str | None]:
    if tf in _DAILY_PLUS_TFS:
        df, source = _fetch_daily_plus(code, tf)
        items = _df_to_items_daily(df) if df is not None and not df.empty else []
    else:
        df, source = _fetch_minute(code, tf)
        items = _df_to_items_minute(df) if df is not None and not df.empty else []
    return items, (source if items else None)


def _build_response(code: str, tf: str, source: str | None, items: list[dict], count: int) -> dict:
    sliced = items[-count:] if items else []
    return {
        "code": code,
        "tf": tf,
        "source": source if sliced else None,
        "items": sliced,
    }


def get_candles(code: str, tf: str, count: int = _DEFAULT_COUNT) -> dict:
    """(code, tf) 캔들 조회. TTL 이내 캐시가 있으면 그대로, 없으면 새로 수집해 캐시에 채운다.

    데이터 없음/수집 실패는 예외를 던지지 않고 items=[]·source=None 인 정상 응답으로 처리한다
    (라우터에서 500 대신 200으로 내려주기 위함).
    """
    safe_count = max(1, min(int(count), _MAX_COUNT))
    cache_key = (code, tf)
    ttl = _cache_ttl(tf)

    cached = _cache.get(cache_key)
    if cached is not None and (time.monotonic() - cached["cached_at"]) < ttl:
        return _build_response(code, tf, cached["source"], cached["items"], safe_count)

    with _lock:
        cached = _cache.get(cache_key)
        if cached is not None and (time.monotonic() - cached["cached_at"]) < ttl:
            return _build_response(code, tf, cached["source"], cached["items"], safe_count)

        try:
            items, source = _fetch(code, tf)
        except Exception as e:
            print(f"[candles] 수집 실패 ({code}, {tf}): {e}")
            items, source = [], None

        _cache[cache_key] = {"items": items, "source": source, "cached_at": time.monotonic()}
        return _build_response(code, tf, source, items, safe_count)
