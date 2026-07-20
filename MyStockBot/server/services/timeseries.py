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
    """점이 target 을 넘으면 균등 간격으로 솎아내되 마지막 점은 항상(중복 없이) 포함한다."""
    if len(curve) <= target:
        return curve
    step = len(curve) // target + 1
    pts = curve[::step]
    if pts[-1] is not curve[-1]:
        pts = pts + [curve[-1]]
    return pts


class PriceDataError(Exception):
    """가격 시계열에 정합성 이상(액면분할 미조정 추정 등)이 감지된 경우."""


def detect_split_anomaly(closes, hi: float = 1.8, lo: float = 0.55):
    """인접 종가 비율이 임계를 벗어나면(분할/역분할·소스 혼용 미조정 추정) 그 인덱스 반환.

    국내 종목은 일일 가격제한(±30%)이 있어 정상 봉의 인접 비율은 [0.7, 1.3] 안이다.
    hi=1.8/lo=0.55 는 2:1 분할(≈0.5)·1:2 역분할(≈2.0) 같은 명백한 미조정만 잡아
    정상 급등락을 오탐하지 않는다. 이상 없으면 None.
    """
    prev = None
    for i, c in enumerate(closes):
        try:
            cf = float(c)
        except (TypeError, ValueError):
            continue
        if cf != cf or cf <= 0:  # NaN/비정상
            continue
        if prev is not None and prev > 0:
            r = cf / prev
            if r > hi or r < lo:
                return i
        prev = cf
    return None
