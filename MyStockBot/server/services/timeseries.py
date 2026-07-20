"""백테스트·DCA 공용 시계열 유틸.

판정 백테스트(backtest.py)와 적립식 백테스트(dca.py)가 공유하는 순수 함수:
epoch 초 → 날짜 문자열 변환, 곡선 다운샘플. 외부 의존 없이 테스트 용이.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TIMEZONE


def epoch_to_date(t, fmt: str = "%Y-%m-%d") -> str | None:
    """epoch 초 → 지정 포맷 날짜 문자열. 파싱 실패 시 None.

    backtest 는 일 단위("%Y-%m-%d"), dca 는 월 단위("%Y-%m")로 호출한다.
    """
    try:
        return datetime.fromtimestamp(int(t), ZoneInfo(TIMEZONE)).strftime(fmt)
    except (TypeError, ValueError, OSError):
        return None


def downsample(curve: list, target: int = 80) -> list:
    """점이 target 을 넘으면 균등 간격으로 솎아내되 마지막 점은 항상 포함한다."""
    if len(curve) > target:
        step = len(curve) // target + 1
        return curve[::step] + [curve[-1]]
    return curve
