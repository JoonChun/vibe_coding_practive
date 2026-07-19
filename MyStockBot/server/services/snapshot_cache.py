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
    "pullback_status", "pullback_reason", "pullback_trend_up",
]


def _to_factors(item: dict) -> dict | None:
    """수집 실패(error 존재) 시 None, 아니면 상세 판정용 팩터 dict."""
    if item.get("error") is not None:
        return None
    return {key: item.get(key) for key in _FACTOR_KEYS}


def _to_snapshot_item(item: dict) -> dict:
    # 지연 import — tick_aggregator.py 가 collector.py 를 참조하고(재무값 재사용),
    # 이 모듈도 collector.py 를 참조하므로 모듈 최상단 import는 순환 위험을 키운다.
    from . import tick_aggregator

    code = item.get("code")
    live_state = tick_aggregator.get_reference_state().get(code) if code else None

    return {
        "code": code,
        "name": item.get("name"),
        "close": item.get("close"),
        "short_view": item.get("short_view"),
        "long_view": item.get("long_view"),
        "source": item.get("source"),
        "error": item.get("error"),
        "change": item.get("change"),
        "change_pct": item.get("change_pct"),
        "factors": _to_factors(item),
        "live": live_state,
    }


async def get_snapshot() -> dict:
    """collector 상태를 읽기만 한다 — 여기서 수집을 트리거하지 않는다."""
    state = collector.get_state()
    if state is None:
        now = datetime.now(ZoneInfo(TIMEZONE))
        return {"generated_at": now.isoformat(), "cache_hit": False, "items": []}

    items = [_to_snapshot_item(item) for item in state.get("items", [])]
    return {
        "generated_at": state.get("generated_at"),
        "cache_hit": True,
        "items": items,
    }
