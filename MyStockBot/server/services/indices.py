"""시장 지수(코스피/코스닥) + 시장 폭(등락종목수) 조회 — read-through 인메모리 캐시.

개별 종목 시세(collector.py)와는 조회 경로가 다르다. 3단 폴백:

  1) **KIS 국내업종 현재지수(FHPUP02100000)** — 전일 대비·대비율을 직접 주고,
     상승/보합/하락/상한/하한 종목 수(시장 폭)까지 같은 응답에 담겨 온다. 1순위.
  2) **KIS 국내업종 일자별 지수(FHKUP03500100)** — 종가 2개를 빼서 등락을 계산한다.
     시장 폭은 없다. 1)이 실패했을 때만.
  3) **yfinance(^KS11/^KQ11)** — 지연·결측이 있고 시장 폭도 없다. 최후 폴백.

어떤 이유(자격증명 없음·TR/필드 불일치·네트워크)로든 앞 단계가 실패하면 예외를 삼키고
다음 단계로 넘어가므로, 항상 값을 낸다(failsafe). 시장 폭은 1)에서만 나오므로 그 외
경로에서는 breadth=None 이고, 화면은 그때 시장 폭 블록을 숨긴다.

get_indices() 는 동기 함수다(내부에서 blocking HTTP 호출) — 라우터에서
asyncio.to_thread 로 감싸 호출한다(routers/stocks.py candles 와 동일 패턴).
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import INDICES_CACHE_TTL_SECONDS, TIMEZONE

logger = logging.getLogger(__name__)

# code → (표시명, KIS 업종 지수 코드, yfinance 심볼)
#   KIS 업종코드: 코스피 종합 "0001", 코스닥 종합 "1001"
_INDEX_DEFS = [
    {"code": "KOSPI", "name": "코스피", "iscd": "0001", "symbol": "^KS11"},
    {"code": "KOSDAQ", "name": "코스닥", "iscd": "1001", "symbol": "^KQ11"},
]

# KIS 지수 일봉 output2 의 지수 종가 후보 필드(문서/버전에 따라 다를 수 있어 순차 시도)
_KIS_CLOSE_KEYS = ["bstp_nmix_prpr", "stck_clpr", "ovrs_nmix_prpr", "bstp_nmix_clpr"]
_KIS_DATE_KEYS = ["stck_bsop_date", "bsop_date"]

_cache: dict = {"generated_at": None, "items": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if f != f else f  # NaN != NaN
    except (TypeError, ValueError):
        return None


def _from_two_closes(value, prev) -> tuple[float, float | None, float | None]:
    value = round(float(value), 2)
    if prev is None or prev == 0:
        return value, None, None
    change = value - prev
    return value, round(change, 2), round(change / prev * 100, 2)


# 전일 대비 부호 코드 → 극성. KIS 전 API 공통 관례(kis_ws._SIGN_POLARITY 와 동일):
#   1 상한가, 2 상승, 3 보합, 4 하한가, 5 하락.
# 원문 숫자에 부호가 이미 있을 수도 없을 수도 있어(WS 쪽에서 확정 불가로 판명), abs() 로
# 절대값을 취한 뒤 이 코드로 극성을 결정한다 — 이중 반전을 막는다.
_SIGN_POLARITY = {"1": 1, "2": 1, "3": 0, "4": -1, "5": -1}

# 시장 폭 필드(FHPUP02100000 output) — chk_inquire_index_price.py COLUMN_MAPPING 원문 기준.
_BREADTH_FIELDS = {
    "up": "ascn_issu_cnt",        # 상승 종목 수
    "flat": "stnr_issu_cnt",      # 보합 종목 수
    "down": "down_issu_cnt",      # 하락 종목 수
    "limit_up": "uplm_issu_cnt",  # 상한 종목 수
    "limit_down": "lslm_issu_cnt",  # 하한 종목 수
}


def _safe_int(val) -> int | None:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _parse_breadth(output: dict) -> dict | None:
    """지수 응답에서 등락종목수를 뽑는다. 상승·하락 둘 다 없으면 None(의미 없는 부분데이터 방지)."""
    parsed = {key: _safe_int(output.get(field)) for key, field in _BREADTH_FIELDS.items()}
    if parsed["up"] is None and parsed["down"] is None:
        return None
    return {k: (v if v is not None else 0) for k, v in parsed.items()}


def _fetch_kis_index_price(iscd: str) -> tuple[float, float | None, float | None, dict | None]:
    """KIS 국내업종 현재지수(FHPUP02100000) → (현재지수, 등락폭, 등락률%, 시장폭).

    일자별 지수와 달리 등락을 직접 주므로 종가 2개를 빼는 계산이 필요 없고, 시장 폭이
    같은 응답에 들어 있다. 실패 시 예외를 던진다(→ 호출부에서 다음 단계 폴백).
    """
    import os

    import kis_auth
    import requests
    from config import (
        KIS_APP_KEY_ENV,
        KIS_APP_SECRET_ENV,
        KIS_INDEX_PRICE_URL,
    )

    token = kis_auth.get_token()  # 자격증명 없으면 RuntimeError
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": os.environ.get(KIS_APP_KEY_ENV, ""),
        "appsecret": os.environ.get(KIS_APP_SECRET_ENV, ""),
        "tr_id": "FHPUP02100000",
    }
    params = {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": iscd}

    kis_auth.kis_throttle()
    resp = requests.get(KIS_INDEX_PRICE_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    output = data.get("output")
    if not output:
        raise RuntimeError(
            f"KIS 현재지수 output 없음: rt_cd={data.get('rt_cd')} msg={data.get('msg1')}"
        )
    # output 이 배열로 오는 변형에 대비(문서상 object 지만 방어).
    if isinstance(output, list):
        output = output[0] if output else {}

    value = _safe_float(output.get("bstp_nmix_prpr"))
    if value is None:
        raise RuntimeError("KIS 현재지수 파싱 실패(bstp_nmix_prpr 없음)")

    polarity = _SIGN_POLARITY.get(str(output.get("prdy_vrss_sign") or "").strip(), 0)
    raw_change = _safe_float(output.get("bstp_nmix_prdy_vrss"))
    raw_pct = _safe_float(output.get("bstp_nmix_prdy_ctrt"))
    change = None if raw_change is None else round(abs(raw_change) * polarity, 2)
    change_pct = None if raw_pct is None else round(abs(raw_pct) * polarity, 2)

    return round(value, 2), change, change_pct, _parse_breadth(output)


def _fetch_kis_index(iscd: str) -> tuple[float, float | None, float | None]:
    """KIS 국내업종 일자별 지수(FHKUP03500100)로 (현재지수, 등락폭, 등락률%) 계산.
    자격증명·TR·필드·네트워크 중 무엇이라도 어긋나면 예외를 던진다(→ 호출부에서 폴백).
    """
    import os

    import kis_auth
    import requests
    from config import (
        KIS_APP_KEY_ENV,
        KIS_APP_SECRET_ENV,
        KIS_INDEX_CHART_URL,
    )

    token = kis_auth.get_token()  # 자격증명 없으면 RuntimeError
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz)
    start = today - timedelta(days=10)
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": os.environ.get(KIS_APP_KEY_ENV, ""),
        "appsecret": os.environ.get(KIS_APP_SECRET_ENV, ""),
        "tr_id": "FHKUP03500100",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": iscd,
        "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": today.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",
    }
    kis_auth.kis_throttle()
    resp = requests.get(KIS_INDEX_CHART_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    out2 = data.get("output2")
    if not out2:
        raise RuntimeError(
            f"KIS 지수 output2 없음: rt_cd={data.get('rt_cd')} msg={data.get('msg1')}"
        )

    def _close_of(row):
        for k in _KIS_CLOSE_KEYS:
            v = _safe_float(row.get(k))
            if v is not None:
                return v
        return None

    def _date_of(row):
        for k in _KIS_DATE_KEYS:
            if row.get(k):
                return str(row[k])
        return ""

    rows = [(_date_of(r), _close_of(r)) for r in out2]
    rows = [(d, c) for d, c in rows if c is not None]
    if not rows:
        raise RuntimeError("KIS 지수 종가 파싱 실패")
    # 날짜 필드명이 응답과 다르면 정렬 기준이 사라져(전부 "") 최신 대신 가장 오래된
    # 봉을 집을 수 있다. 신뢰 가능한 8자리 날짜가 없으면 정렬을 포기하고 폴백을 유도한다.
    if not all(len(d) == 8 and d.isdigit() for d, _ in rows):
        raise RuntimeError("KIS 지수 날짜 파싱 실패(정렬 불가) — yfinance 폴백")
    rows.sort(key=lambda x: x[0])  # 날짜 오름차순
    value = rows[-1][1]
    prev = rows[-2][1] if len(rows) >= 2 else None
    return _from_two_closes(value, prev)


def _fetch_yf_index(symbol: str) -> tuple[float, float | None, float | None]:
    """yfinance 폴백 — 최근 종가 2개로 (현재지수, 등락폭, 등락률%) 계산."""
    import yfinance as yf  # 지연 import

    hist = yf.Ticker(symbol).history(period="5d", interval="1d")
    if hist is None or hist.empty or "Close" not in hist.columns:
        raise RuntimeError(f"지수 시세 없음: {symbol}")
    closes = [c for c in hist["Close"].tolist() if _safe_float(c) is not None]
    if not closes:
        raise RuntimeError(f"유효 종가 없음: {symbol}")
    value = _safe_float(closes[-1])
    prev = _safe_float(closes[-2]) if len(closes) >= 2 else None
    if value is None:
        raise RuntimeError(f"현재 지수 파싱 실패: {symbol}")
    return _from_two_closes(value, prev)


def _fetch_one(d: dict) -> tuple[float, float | None, float | None, dict | None, str]:
    """현재지수(시장폭 포함) → 일자별 지수 → yfinance 순으로 폴백.

    반환에 breadth 와 source 포함. 시장 폭은 1순위 경로에서만 나오므로 폴백하면 None 이다.
    전부 실패하면 예외 전파(호출부가 종목별로 격리).
    """
    try:
        value, change, pct, breadth = _fetch_kis_index_price(d["iscd"])
        return value, change, pct, breadth, "kis"
    except Exception as e:
        logger.warning(f"[indices] {d['code']} KIS 현재지수 실패, 일자별 지수로 폴백: {e}")

    try:
        value, change, pct = _fetch_kis_index(d["iscd"])
        # 일자별 지수에는 등락종목수가 없다 → 시장 폭 블록은 화면에서 숨겨진다.
        return value, change, pct, None, "kis"
    except Exception as e:
        logger.warning(f"[indices] {d['code']} KIS 일자별 지수 실패, yfinance 폴백: {e}")

    value, change, pct = _fetch_yf_index(d["symbol"])
    return value, change, pct, None, "yfinance"


def _fetch_all() -> list[dict]:
    items: list[dict] = []
    for d in _INDEX_DEFS:
        try:
            value, change, change_pct, breadth, source = _fetch_one(d)
            items.append({
                "code": d["code"], "name": d["name"],
                "value": value, "change": change, "change_pct": change_pct,
                "breadth": breadth,
                "source": source, "error": None,
            })
        except Exception as e:  # 한 지수 실패가 다른 지수를 막지 않도록 개별 격리
            logger.warning(f"[indices] {d['code']} 조회 실패: {e}")
            items.append({
                "code": d["code"], "name": d["name"],
                "value": None, "change": None, "change_pct": None,
                "breadth": None,
                "source": None, "error": str(e),
            })
    return items


def get_indices() -> dict:
    """read-through 캐시. 신선하면 캐시 반환, stale/없으면 재조회 후 갱신.

    fetch 는 락 밖에서 수행해 요청이 서로를 오래 블로킹하지 않게 한다(간헐적 중복
    조회는 허용 — 2개 심볼·TTL 고려 시 무해).
    """
    now = time.monotonic()
    with _cache_lock:
        if (
            _cache["items"] is not None
            and (now - _cache["fetched_at"]) < INDICES_CACHE_TTL_SECONDS
        ):
            return {
                "generated_at": _cache["generated_at"],
                "cache_hit": True,
                "items": _cache["items"],
            }

    items = _fetch_all()
    generated_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
    with _cache_lock:
        _cache["items"] = items
        _cache["generated_at"] = generated_at
        _cache["fetched_at"] = time.monotonic()

    return {"generated_at": generated_at, "cache_hit": False, "items": items}
