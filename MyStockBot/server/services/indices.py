"""시장 지수(코스피/코스닥) 조회 — read-through 인메모리 캐시.

개별 종목 시세(collector.py)와는 조회 경로가 다르다. 여기서는 yfinance 심볼
(^KS11=코스피, ^KQ11=코스닥)로 최근 종가 2개를 받아 현재지수·전일 대비 등락을 계산한다.

향후 KIS 국내업종 현재지수 TR로 승격 가능하도록 fetch 계층을 분리해 두었다
(현재는 yfinance 단독 — 지연·결측 가능, 지수 대시보드 참고용으로 충분).

get_indices() 는 동기 함수다(내부에서 blocking HTTP 호출) — 라우터에서
asyncio.to_thread 로 감싸 호출한다(routers/stocks.py candles 와 동일 패턴).
"""
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from config import INDICES_CACHE_TTL_SECONDS, TIMEZONE

# code → (표시명, yfinance 심볼)
_INDEX_DEFS = [
    {"code": "KOSPI", "name": "코스피", "symbol": "^KS11"},
    {"code": "KOSDAQ", "name": "코스닥", "symbol": "^KQ11"},
]

_cache: dict = {"generated_at": None, "items": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if f != f else f  # NaN != NaN
    except (TypeError, ValueError):
        return None


def _fetch_one(symbol: str) -> tuple[float | None, float | None, float | None]:
    """최근 종가 2개로 (현재지수, 등락폭, 등락률%) 계산. 조회 실패 시 예외 전파."""
    import yfinance as yf  # 지연 import — 의존성 없는 환경에서도 모듈 import 는 성공

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

    if prev is None or prev == 0:
        return round(value, 2), None, None
    change = value - prev
    return round(value, 2), round(change, 2), round(change / prev * 100, 2)


def _fetch_all() -> list[dict]:
    items: list[dict] = []
    for d in _INDEX_DEFS:
        try:
            value, change, change_pct = _fetch_one(d["symbol"])
            items.append({
                "code": d["code"], "name": d["name"],
                "value": value, "change": change, "change_pct": change_pct,
                "source": "yfinance", "error": None,
            })
        except Exception as e:  # 한 지수 실패가 다른 지수를 막지 않도록 개별 격리
            print(f"[indices] {d['code']} 조회 실패: {e}")
            items.append({
                "code": d["code"], "name": d["name"],
                "value": None, "change": None, "change_pct": None,
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
