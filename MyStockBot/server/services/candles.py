"""멀티 타임프레임 캔들 서비스.

GET /api/stocks/{code}/candles 라우트의 비즈니스 로직.
- 소스 라우팅: 일봉+(1d/1w/1M/1y)는 KIS 기간별시세 우선, 실패 시 yfinance 폴백(1y는 폴백 없음).
  분봉(1m/5m/15m/30m/60m)은 yfinance 직접 조회. 120m/240m은 60분봉을 서버에서 리샘플.
- epoch 변환: 일봉+ 는 KST 자정 기준, 분봉은 원본 tz-aware 타임스탬프의 실제 시각 기준.
- 영속 저장소(db.candles) read-through: 신선(분봉 60초·일봉+ 600초) 이내면 저장소에서
  바로 서빙, stale/없음이면 fetch → upsert_candles → 저장소에서 재조회해 서빙(기존
  이력과 병합된 채로 나간다 — collector.py가 채워둔 데이터와도 자연히 합쳐짐).
  fetch 실패 시 저장소에 남은 값(낡아도)을 서빙, 그마저 없으면 빈 items(기존 계약).
"""
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import crawler
import db
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

_MINUTE_FRESH_SECONDS = 60
_DAILY_FRESH_SECONDS = 600

_DEFAULT_COUNT = 150
_MAX_COUNT = 300

# (code, tf) → 이번 서버 세션에서 마지막으로 저장소에 upsert한 fetch의 source("kis"|"yfinance").
# 별도 candles_meta 테이블 없이 과설계를 피하기 위한 인메모리 기록 — 서버 재시작 후
# 저장소가 신선해서 fetch 없이 바로 서빙하는 경우엔 이 기록이 비어 있으므로 "store"로 대체한다.
_last_source: dict[tuple[str, str], str] = {}
_source_lock = threading.Lock()


def _fresh_threshold(tf: str) -> int:
    return _MINUTE_FRESH_SECONDS if tf in _MINUTE_TFS else _DAILY_FRESH_SECONDS


def _remembered_source(code: str, tf: str) -> str:
    with _source_lock:
        return _last_source.get((code, tf), "store")


def _remember_source(code: str, tf: str, source: str | None) -> None:
    if source is None:
        return
    with _source_lock:
        _last_source[(code, tf)] = source


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


def get_candles(code: str, tf: str, count: int = _DEFAULT_COUNT) -> dict:
    """(code, tf) 캔들 조회. 영속 저장소(db.candles) read-through.

    저장소가 신선(분봉 60초·일봉+ 600초 이내)하면 fetch 없이 바로 서빙한다.
    stale/없으면 기존 소스 라우팅으로 새로 수집해 저장소에 upsert 후, 저장소에서
    다시 읽어 서빙(누적 이력과 자연히 병합됨). fetch 마저 실패하면 저장소에 남은
    낡은 데이터라도 서빙하고, 그마저 없으면 items=[]·source=None 인 정상 응답으로
    처리한다(라우터에서 500 대신 200으로 내려주기 위함 — 기존 계약 그대로).
    """
    safe_count = max(1, min(int(count), _MAX_COUNT))

    age = db.get_candles_age_seconds(code, tf)
    if age is not None and age < _fresh_threshold(tf):
        stored = db.get_candles_store(code, tf, safe_count)
        return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

    fetch_error = False
    try:
        items, source = _fetch(code, tf)
    except Exception as e:
        print(f"[candles] 수집 실패 ({code}, {tf}): {e}")
        items, source = [], None
        fetch_error = True

    if items:
        db.upsert_candles(code, tf, items)
        _remember_source(code, tf, source)
        stored = db.get_candles_store(code, tf, safe_count)
        return _build_response(code, tf, source, stored, safe_count)

    # fetch 실패/빈 데이터 — 저장소에 낡은 값이라도 있으면 그거라도 서빙.
    stored = db.get_candles_store(code, tf, safe_count)
    if stored:
        print(f"[candles] 최신 수집 실패 — 저장소의 낡은 데이터로 서빙 ({code}, {tf})")
        return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

    # 데이터가 아예 없음: fetch 예외였는지(소스 장애) 빈 응답이었는지 구분해 전달.
    return _build_response(code, tf, None, [], safe_count, fetch_error=fetch_error)
