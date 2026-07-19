"""멀티 타임프레임 캔들 서비스.

GET /api/stocks/{code}/candles 라우트의 비즈니스 로직.
- 소스 라우팅:
  - 일봉+(1d/1w/1M)는 KIS 기간별시세 페이지네이션(fetch_kis_ohlcv_paged, 날짜구간 역행
    반복호출로 target_count까지 누적) 우선, 실패 시 yfinance 폴백. 1y는 기존과 동일하게
    단일 호출(fetch_kis_ohlcv) 유지, 폴백 없음.
  - 분봉(1m/5m/15m/30m/60m)은 KIS 당일분봉(fetch_kis_minutes, 1분봉) 우선 조회 후 서버에서
    해당 tf로 리샘플, 실패/빈 데이터(장전·휴장·소형주 등)면 yfinance 직접 조회로 폴백.
  - 120m/240m은 60분봉(위 우선순위로 확보한 것)을 서버에서 다시 리샘플.
- epoch 변환: 일봉+ 는 KST 자정 기준. yfinance 분봉은 원본 tz-aware 타임스탬프의 실제 시각
  기준, KIS 분봉은 'YYYYMMDDHHMM' 문자열을 KST로 직접 파싱(KIS 데이터는 항상 국내 거래소
  기준이라 안전).
- count 상한: 1d/1w/60m/120m/240m 는 최대 1000(과거 깊이 허용), 그 외 분봉(1m/5m/15m/30m)은
  기존 300 유지(yfinance 원천 자체가 60일 이하라 상한을 올려도 의미 없음).
- 영속 저장소(db.candles) read-through: 신선(분봉 60초·일봉+ 600초) 이내면 저장소에서
  바로 서빙, stale/없음이면 fetch → upsert_candles → 저장소에서 재조회해 서빙(기존
  이력과 병합된 채로 나간다 — collector.py가 채워둔 데이터와도 자연히 합쳐짐).
  fetch 실패 시 저장소에 남은 값(낡아도)을 서빙, 그마저 없으면 빈 items(기존 계약).
- 60m 깊이 게이트: KIS 당일분봉은 오늘치만 주므로, 저장소가 신선해도(60초 이내) 요청
  개수보다 얕으면(=여태 KIS로만 채워져 과거가 안 쌓인 상태) yfinance 730d(yf 60분 간격
  하드 한계) 강제 수집을 1회 시도해 병합한다(KIS 데이터와는 (code,tf,t) PK REPLACE라
  안전하게 공존). 원천 자체가 얕은 종목(신규상장 등)의 무한 재수집을 막기 위해 쿨다운
  (_DEEP_FETCH_COOLDOWN_SECONDS)을 둔다. 120m/240m 은 이 게이트를 직접 갖지 않고
  get_candles(...,"60m",...) 를 재귀 호출해 리샘플 입력을 얻으므로, 60m 이 깊어지면
  자동으로 함께 깊어진다.
"""
import threading
import time
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
# 60m 은 "730d"(yfinance 60분 간격 조회의 하드 한계) — 과거 깊이 확장을 위해 "6mo"에서 상향.
# ("2y"는 yfinance 쪽에서 60분 간격 기준 한계 경계상 거부될 수 있어 "730d" 리터럴을 그대로 쓴다.)
_YF_DIRECT_MAP = {
    "1m": ("1m", "7d"),
    "5m": ("5m", "60d"),
    "15m": ("15m", "60d"),
    "30m": ("30m", "60d"),
    "60m": ("60m", "730d"),
}

# 120m/240m 은 60분봉(KIS 1분봉 리샘플 또는 yfinance) 을 서버에서 다시 리샘플
# (버킷 크기 = 분 단위, resample_items 가 clock-aligned floor 로 그룹핑).
_RESAMPLE_UNIT = {"120m": 120, "240m": 240}

# 딥 수집(과거 깊이 확장) 대상 분봉 tf. get_candles 깊이 게이트에서 _DAILY_PLUS_TFS 와
# 별도로 취급한다(1M/1y 는 기존 그대로 _DAILY_PLUS_TFS 소속 게이트만 적용받고, 이 집합에는
# 들어오지 않는다 — 두 집합의 목적이 다름에 주의).
_DEEP_MINUTE_TFS = {"60m", "120m", "240m"}

# KIS 당일분봉(1분)을 tf 단위로 묶을 때의 리샘플 unit(1분 캔들 몇 개를 하나로 묶는지).
_KIS_MINUTE_UNIT = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}

_MINUTE_TFS = {"1m", "5m", "15m", "30m", "60m", "120m", "240m"}
_DAILY_PLUS_TFS = {"1d", "1w", "1M", "1y"}

VALID_TFS = _MINUTE_TFS | _DAILY_PLUS_TFS

_MINUTE_FRESH_SECONDS = 60
_DAILY_FRESH_SECONDS = 600

_DEFAULT_COUNT = 150
_MAX_COUNT = 300         # 1m/5m/15m/30m·1M 상한(기존 유지 — yfinance 원천 한계가 60일 이하라
                         # 깊이 확장 자체가 의미 없는 tf들)
_MAX_COUNT_DEEP = 1000   # 1d/1w/60m/120m/240m 전용 상한(과거 깊이 허용 — 1d/1w는 페이지네이션,
                         # 60m/120m/240m 은 yfinance 730d 딥 수집으로 확보 가능해짐)
_DEEP_COUNT_TFS = {"1d", "1w", "60m", "120m", "240m"}

# (code, tf) → 이번 서버 세션에서 마지막으로 저장소에 upsert한 fetch의 source("kis"|"yfinance").
# 별도 candles_meta 테이블 없이 과설계를 피하기 위한 인메모리 기록 — 서버 재시작 후
# 저장소가 신선해서 fetch 없이 바로 서빙하는 경우엔 이 기록이 비어 있으므로 "store"로 대체한다.
_last_source: dict[tuple[str, str], str] = {}
_source_lock = threading.Lock()

# 60m 딥 수집(yfinance 730d 강제) 재시도 쿨다운(초) — collector.py 의
# _60m_bootstrap_cooldown 과 동일한 in-memory 쿨다운 패턴. 원천 자체가 얕은 종목
# (신규상장 등)이 신선도 게이트를 매번 통과할 때마다 외부 호출을 반복하지 않도록 방어.
_DEEP_FETCH_COOLDOWN_SECONDS = 600
_deep_fetch_attempted_at: dict[tuple[str, str], float] = {}
_deep_fetch_lock = threading.Lock()


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
    """딥 수집(60m 강제 yfinance 730d) 시도 가능 여부. 쿨다운 내 재시도면 False를 돌려주고
    아무것도 기록하지 않는다(그 사이엔 저장소가 얕아도 그대로 서빙) — 원천 자체가 얕은
    종목이 매 요청마다 외부 호출을 반복하지 않도록 방어한다. True를 돌려줄 때는 시도
    시각을 함께 기록한다(collector._bootstrap_60m_if_needed 와 동일 관례 — 성공 여부와
    무관하게 시도 자체를 기록해 쿨다운을 재시작한다)."""
    now = time.monotonic()
    with _deep_fetch_lock:
        last = _deep_fetch_attempted_at.get((code, tf))
        if last is not None and (now - last) < _DEEP_FETCH_COOLDOWN_SECONDS:
            return False
        _deep_fetch_attempted_at[(code, tf)] = now
        return True


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


def _kis_minute_epoch(date_str) -> int | None:
    """'YYYYMMDDHHMM' 문자열(KST, KIS 당일분봉)을 Unix epoch(초)로 변환. 파싱 실패 시 None."""
    try:
        dt = datetime.strptime(str(date_str)[:12], "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _df_to_items_minute_kis(df: pd.DataFrame) -> list[dict]:
    """crawler.fetch_kis_minutes 결과 전용 변환. 이 df는 (yfinance 분봉과 달리) 의미 있는
    tz-aware 인덱스가 없고 정수 RangeIndex이므로, 'date'='YYYYMMDDHHMM' 문자열을 직접
    KST로 파싱한다(KIS 데이터는 항상 국내 거래소 기준이라 문자열 재해석 위험이 없음)."""
    items = []
    for _, row in df.iterrows():
        t = _kis_minute_epoch(row.get("date"))
        if t is None:
            continue
        items.append(_row_to_item(row, t))
    return items


def resample_items(items: list[dict], unit_minutes: int) -> list[dict]:
    """t 오름차순 캔들 items를 unit_minutes 크기의 clock-aligned(절대 시각 기준) 버킷으로
    묶어 상위 tf 캔들로 합성한다. candles.py 내부(120m/240m ← 60m)뿐 아니라
    collector.py(60m ← KIS 1분봉)에서도 재사용하는 공용 유틸.

    버킷 경계는 items 리스트의 첫 항목(=조회창 시작)이 아니라 절대 epoch을
    floor(t / (unit_minutes*60)) * (unit_minutes*60) 로 계산한다. KST epoch 0(1970-01-01
    00:00 UTC)이 정확히 1970-01-01 09:00 KST이고, 지원하는 모든 버킷 크기(1/5/15/30/60/120/240분)
    가 하루(86400초)를 나누어떨어지므로, 이 floor 연산은 조회창이 어디서 시작하든 항상
    장 시작(09:00 KST) 기준과 동일한 버킷 경계를 만들어낸다.
    (이전에는 조회창 시작 위치를 기준으로 positional하게 묶어, 오후에 조회창이 밀리면
    같은 실제 구간인데도 재조회 시각마다 버킷 시작 epoch(t)이 달라져 candles PK
    (code, tf, t) REPLACE가 아니라 매번 새 행으로 쌓이는 문제가 있었다 — 이를 해결한다.)

    open=버킷 첫 값, high=버킷 최댓값, low=버킷 최솟값, close=버킷 마지막 값, volume=버킷 합.
    unit_minutes<=1 이거나 items가 비면 입력을 그대로 반환한다.
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


def _fetch_daily_plus(code: str, tf: str, count: int) -> tuple[pd.DataFrame | None, str | None]:
    period, lookback_days = _KIS_PERIOD_MAP[tf]

    try:
        token = kis_auth.get_token()
    except Exception as e:
        print(f"[candles] KIS 토큰 발급 실패({code},{tf}) — yfinance 폴백 경로로 진행: {e}")
        token = None

    if token is not None:
        if tf == "1y":
            # 년봉은 기존과 동일하게 단일 호출 유지(스펙 명시 — 페이지네이션 미적용).
            df = crawler.fetch_kis_ohlcv(code, token, period=period, lookback_days=lookback_days)
        else:
            df = crawler.fetch_kis_ohlcv_paged(code, token, period=period, target_count=count)
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


def _fetch_kis_minute_items(code: str, tf: str) -> list[dict]:
    """KIS 당일분봉(1분) 조회 → tf 단위로 리샘플. 토큰 실패·데이터없음(장전·휴장·소형주
    정상거래무 등)이면 빈 리스트를 돌려줘 호출부가 yfinance 폴백으로 이어가게 한다."""
    try:
        token = kis_auth.get_token()
    except Exception as e:
        print(f"[candles] KIS 토큰 발급 실패({code},{tf}) — yfinance 폴백 경로로 진행: {e}")
        return []

    df1 = crawler.fetch_kis_minutes(code, token)
    if df1 is None or df1.empty:
        return []

    one_min_items = _df_to_items_minute_kis(df1)
    if not one_min_items:
        return []

    return resample_items(one_min_items, _KIS_MINUTE_UNIT.get(tf, 1))


def _fetch_direct_minute(code: str, tf: str) -> tuple[list[dict], str | None]:
    """1m/5m/15m/30m/60m 공통 경로: KIS 당일분봉(1분) 리샘플 우선, 실패/빈 데이터면
    yfinance 직접 조회로 폴백."""
    kis_items = _fetch_kis_minute_items(code, tf)
    if kis_items:
        return kis_items, "kis"

    interval, period = _YF_DIRECT_MAP[tf]
    df = crawler.fetch_yf_ohlcv(code, interval=interval, period=period)
    if df is None or df.empty:
        return [], None
    return _df_to_items_minute(df), "yfinance"


def _fetch_deep_60m(code: str) -> tuple[list[dict], str | None]:
    """60m 전용 딥 수집 — KIS 당일분봉은 오늘치만 제공해 과거 깊이 확장에 못 쓰므로,
    yfinance 직접 조회(730d, yf 60분 간격 하드 한계)로 KIS 여부와 무관하게 강제 수집한다.
    get_candles 의 60m 깊이 게이트(저장소가 신선하지만 요청보다 얕을 때)에서만 호출된다."""
    interval, period = _YF_DIRECT_MAP["60m"]
    df = crawler.fetch_yf_ohlcv(code, interval=interval, period=period)
    if df is None or df.empty:
        return [], None
    return _df_to_items_minute(df), "yfinance"


def _fetch_minute(code: str, tf: str, count: int) -> tuple[list[dict], str | None]:
    if tf in _RESAMPLE_UNIT:
        # 120m/240m 은 60m 을 다시 리샘플한다. 자체 라이브 조회 대신 get_candles(...,"60m",...)
        # 를 재귀 호출해 60m 전용 신선도·깊이 게이트(딥 수집·쿨다운 포함)를 그대로 재사용
        # 한다 — 60m 저장소가 깊어지면 120m/240m 도 로직 중복 없이 자동으로 깊어진다.
        unit = _RESAMPLE_UNIT[tf]
        base = get_candles(code, "60m", count * (unit // 60))
        base_items = base.get("items") or []
        if not base_items:
            return [], None
        return resample_items(base_items, unit), base.get("source")

    return _fetch_direct_minute(code, tf)


def _fetch(code: str, tf: str, count: int) -> tuple[list[dict], str | None]:
    if tf in _DAILY_PLUS_TFS:
        df, source = _fetch_daily_plus(code, tf, count)
        items = _df_to_items_daily(df) if df is not None and not df.empty else []
        return items, (source if items else None)

    items, source = _fetch_minute(code, tf, count)
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
    """(code, tf) 캔들 조회. 영속 저장소(db.candles) read-through.

    저장소가 신선(분봉 60초·일봉+ 600초 이내)하면 fetch 없이 바로 서빙한다.
    stale/없으면 기존 소스 라우팅으로 새로 수집해 저장소에 upsert 후, 저장소에서
    다시 읽어 서빙(누적 이력과 자연히 병합됨). fetch 마저 실패하면 저장소에 남은
    낡은 데이터라도 서빙하고, 그마저 없으면 items=[]·source=None 인 정상 응답으로
    처리한다(라우터에서 500 대신 200으로 내려주기 위함 — 기존 계약 그대로).
    """
    safe_count = max(1, min(int(count), _max_count_for(tf)))

    age = db.get_candles_age_seconds(code, tf)
    if age is not None and age < _fresh_threshold(tf):
        stored = db.get_candles_store(code, tf, safe_count)

        if tf in _DAILY_PLUS_TFS:
            # 일봉+(1d/1w/1M/1y) 는 저장소가 신선해도 요청 개수보다 얕으면(과거가
            # 아직 안 쌓임) 페이지네이션으로 더 깊이 수집한다 — 신선도만 보면 얕은
            # 데이터가 고착됨. (기존 게이트 그대로 — 손대지 않음.)
            if len(stored) >= safe_count:
                return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)
            # else: 아래 공용 _fetch() 로 계속 진행(기존 1d/1w/1M/1y 흐름 그대로).

        elif tf in _DEEP_MINUTE_TFS:
            # 60m/120m/240m 도 저장소가 신선해도 요청 개수보다 얕으면 딥 수집을 시도한다.
            # KIS 당일분봉이 늘 신선하게 유지해 신선도만으로는 얕음이 영원히 안 걸러지므로
            # (다른 분봉과 달리) 여기서 명시적으로 깊이를 체크한다.
            if len(stored) >= safe_count:
                return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

            if tf == "60m":
                # KIS 당일분봉은 오늘치만 주므로 이 경로만으로는 절대 깊어지지 않는다 —
                # 쿨다운을 거쳐 yfinance 730d 강제 딥 수집을 1회 시도한다(원천 고갈 방어).
                if _deep_fetch_cooldown_ok(code, tf):
                    deep_items, deep_source = _fetch_deep_60m(code)
                    if deep_items:
                        db.upsert_candles(code, tf, deep_items)
                        _remember_source(code, tf, deep_source)
                        print(f"[candles] 60분봉 딥 수집 발동({code}) — yfinance 730d, {len(deep_items)}건 upsert")
                        stored = db.get_candles_store(code, tf, safe_count)
                return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

            # 120m/240m 은 아래 공용 _fetch() → get_candles(...,"60m",...) 재귀를 통해
            # 60m 딥 게이트를 그대로 태운다(위 60m 분기와 동일 사상, 로직 중복 없음).

        else:
            return _build_response(code, tf, _remembered_source(code, tf), stored, safe_count)

    try:
        items, source = _fetch(code, tf, safe_count)
    except Exception as e:
        print(f"[candles] 수집 실패 ({code}, {tf}): {e}")
        items, source = [], None

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

    return _build_response(code, tf, None, [], safe_count)


# ────────────────────────────────────────────
# 코스피 지수(^KS11) 캐싱 — Phase 3 "그날의 나" What-if 코스피 병치용.
# 위 get_candles()(종목 캔들) 로직은 무변경 — 별도 함수로 병치한다. db.upsert_candles/
# get_candles_store/get_candles_age_seconds 는 code 형식을 검증하지 않으므로 pseudo-code
# "^KS11" 을 그대로 (code, tf) PK 로 통용할 수 있다(정도전 설계 확인 완료).
# ────────────────────────────────────────────

_INDEX_CODE = "^KS11"
_INDEX_TF = "1d"
_INDEX_YF_PERIOD = "max"


def get_index_candles(count: int = 1000) -> list[dict]:
    """코스피 지수(^KS11) 일봉 read-through 캐시.

    신선도 게이트는 일봉+ 와 동일한 _DAILY_FRESH_SECONDS(600초)를 재사용한다. 저장소가
    신선하고 요청 개수만큼 쌓여 있으면 fetch 없이 바로 서빙. stale 이거나 얕으면
    crawler.fetch_yf_index_ohlcv(period="max")로 1회 넉넉히 적재(yfinance 지수 데이터는
    KIS 대상이 아니므로 KIS 경로 없음 — yfinance 단일 소스). fetch 실패 시 저장소에 남은
    값(낡아도)을 그대로 서빙, 그마저 없으면 빈 리스트(호출부 whatif.py가 kospi=null 로
    처리해 whatif 응답 전체를 막지 않는다).
    """
    safe_count = max(1, min(int(count), _MAX_COUNT_DEEP))

    age = db.get_candles_age_seconds(_INDEX_CODE, _INDEX_TF)
    if age is not None and age < _DAILY_FRESH_SECONDS:
        stored = db.get_candles_store(_INDEX_CODE, _INDEX_TF, safe_count)
        if len(stored) >= safe_count:
            return stored
        # else: 얕음 — 아래에서 재적재 시도.

    try:
        df = crawler.fetch_yf_index_ohlcv(_INDEX_CODE, interval="1d", period=_INDEX_YF_PERIOD)
    except Exception as e:
        print(f"[candles] 코스피 지수(^KS11) 수집 실패: {e}")
        df = None

    if df is not None and not df.empty:
        items = _df_to_items_daily(df)
        if items:
            db.upsert_candles(_INDEX_CODE, _INDEX_TF, items)
            print(f"[candles] 코스피 지수(^KS11) 적재 — {len(items)}건 upsert")

    return db.get_candles_store(_INDEX_CODE, _INDEX_TF, safe_count)
