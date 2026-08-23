"""스냅샷 제공부 — 수집(collector.py)과 분리된 순수 read 전용 계층.

실제 fetch/지표계산은 collector.py 백그라운드 루프가 전담한다. 여기서는 그 결과
(collector.get_state())를 기존 GET /api/snapshot 응답 계약
{"generated_at","cache_hit","items":[...]} 으로 변환해 돌려줄 뿐이다.
부팅 직후(첫 수집 사이클 완료 전)엔 상태가 없으므로 items=[]·cache_hit=false.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TIMEZONE

from . import collector

_FACTOR_KEYS = [
    "macd_1d", "rsi_1d", "rsi_value_1d",
    "macd_60m", "rsi_60m", "rsi_value_60m",
    "bb_upper", "bb_mid", "bb_lower",
    "per", "pbr", "roe",
    "short_score", "long_score",
    "bars_60m",
    "pullback_status", "pullback_reason", "pullback_trend_up", "pullback_checks",
]


def _to_factors(item: dict) -> dict | None:
    """수집 실패(error 존재) 시 None, 아니면 상세 판정용 팩터 dict.

    기여요인 분해(breakdown)를 여기서 함께 만들어 내려보낸다 — 예전에는 프론트가
    점수표·임계값·설명문을 TS 로 복제해 스스로 계산했고(web/src/utils/factorScoring.ts),
    그래서 화면에 보이는 합계가 실제 판정 근거와 어긋날 수 있었다. 이제 계산 지점은
    indicators.factor_rows 한 곳뿐이고 화면은 그것을 그린다.
    """
    if item.get("error") is not None:
        return None

    import indicators

    factors = {key: item.get(key) for key in _FACTOR_KEYS}
    factors["breakdown_short"] = indicators.factor_rows(item, "short")
    factors["breakdown_long"] = indicators.factor_rows(item, "long")
    return factors


def _to_snapshot_item(item: dict) -> dict:
    return {
        "code": item.get("code"),
        "name": item.get("name"),
        "close": item.get("close"),
        "short_view": item.get("short_view"),
        "long_view": item.get("long_view"),
        "source": item.get("source"),
        "error": item.get("error"),
        "change": item.get("change"),
        "change_pct": item.get("change_pct"),
        "factors": _to_factors(item),
    }


def _rules_meta() -> dict:
    """판정 임계값을 응답에 실어 보낸다(항목마다가 아니라 응답 1회).

    프론트가 `TAB_THRESHOLD = {short: 2, long: 3}` 을 복제해 두고 "합계가 +3 이상이면 매수"
    라는 틀린 설명을 렌더하던 문제를 없앤다 — 실제 규칙은 +1 이상 매수, +3 이상 강력매수다.
    """
    import indicators

    return indicators.decision_thresholds()


async def get_snapshot() -> dict:
    """collector 상태를 읽기만 한다 — 여기서 수집을 트리거하지 않는다."""
    state = collector.get_state()
    rules_meta = _rules_meta()
    if state is None:
        now = datetime.now(ZoneInfo(TIMEZONE))
        return {
            "generated_at": now.isoformat(),
            "cache_hit": False,
            "items": [],
            "rules": rules_meta,
        }

    items = [_to_snapshot_item(item) for item in state.get("items", [])]
    return {
        "generated_at": state.get("generated_at"),
        "cache_hit": True,
        "items": items,
        "rules": rules_meta,
    }
