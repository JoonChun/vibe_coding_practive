"""판정 규칙의 단일 소스 — 지표 라벨 문자열 · 점수표 · 등급 임계값.

## 왜 이 파일이 생겼나
같은 규칙이 세 곳에 손으로 복제되어 있었다:
  1. src/indicators.py            — 라벨 생성 + 점수표 + 임계값 (원본)
  2. server/services/backtest.py  — 라벨 생성 규칙 재구현 (과거 시점 재적용용)
  3. web/src/utils/factorScoring.ts — 점수표·임계값·설명문 TS 재구현 (화면 표시용)
복제본이 어긋나도 **아무도 실패하지 않는다**. 점수표 lookup 은 `.get(label, 0)` 이라
라벨 문자열이 하나만 달라져도 조용히 전부 0점(=관망)이 되고, TS 쪽은 라벨 타입이
`string | null` 이라 컴파일 에러도 나지 않는다.

그래서 라벨 문자열과 점수 규칙을 여기 한 곳에 모으고, 나머지는 전부 여기서 가져간다.
프론트는 더 이상 점수를 재계산하지 않는다 — 백엔드가 계산한 기여요인 분해를 받아 그린다
(server/services/collector.py → snapshot 응답의 factors.breakdown).

## 규칙을 바꾸려는 사람에게
점수 가중치와 임계값은 **검증된 값이 아니다.** 손으로 정한 값이고, 이 저장소에는 그것을
데이터로 확인한 기록이 없다. 바꾸고 싶으면 숫자를 여기서 고치기 전에
`scripts/evaluate_rules.py` 로 근거를 만들어라 — 그 도구가 "지금 데이터로는 이 정도 크기의
차이를 검출할 수 없다"고 답할 가능성이 높고, 그렇다면 바꾸지 않는 것이 정답이다.
"""
from dataclasses import dataclass, field

# ────────────────────────────────────────────
# 지표 라벨 문자열 — 이 값들이 곧 API 표면이다.
#
# 백엔드 판정 점수 lookup, 백테스트 라벨 재생성, 프론트 칩·기여요인 표시가 모두 이 문자열에
# 의존한다. 바꾸면 조용히 전부 0점이 되므로 **개명하지 말 것**. 부득이하면 이 파일과
# server/services/backtest.py, web/src/types.ts 를 같은 커밋에서 함께 바꿔야 한다.
# ────────────────────────────────────────────

NO_DATA = "데이터부족"

MACD_GOLDEN_CROSS = "골든크로스(진입)"
MACD_DEAD_CROSS = "데드크로스(매도)"
MACD_ABOVE = "진입구간"
MACD_BELOW = "매도구간"

RSI_OVERSOLD_ZONE = "과매도(진입)"
RSI_OVERBOUGHT_ZONE = "과매수(매도)"
RSI_NEUTRAL = "중립"

# 5단계 판정 라벨 — 프론트 SignalChip/DistributionStrip/DECISION_RANK 와 문자열 일치 필수.
VIEW_STRONG_BUY = "강력매수"
VIEW_BUY = "매수"
VIEW_HOLD = "관망"
VIEW_SELL = "매도"
VIEW_STRONG_SELL = "강력매도"

# 판정 없음으로 취급하는 입력값 — None(지표 계산 예외)과 "데이터부족" 문자열을 같은 등급으로 본다.
NO_DATA_INPUTS = (None, NO_DATA)

# 5단계 판정을 3개 '측(side)'으로 묶는다 — 알림이 구조적 강등을 신호로 오독하지 않도록.
#
# 골든크로스(+2)는 **다음 봉에서 필연적으로** 진입구간(+1)으로 내려앉는다(교차는 한 봉만
# 성립한다). 즉 강력매수→매수 전환은 시장이 바뀐 게 아니라 라벨 정의가 만들어낸 사건이고,
# 골든크로스마다 두 번째 알림이 자동으로 따라온다. 데드크로스→매도구간도 대칭으로 같다.
# 측이 바뀔 때만 알리면 이 잡음이 구조적으로 사라진다(server/services/alerts.py 참고).
_VIEW_SIDES = {
    VIEW_STRONG_BUY: "buy",
    VIEW_BUY: "buy",
    VIEW_HOLD: "hold",
    VIEW_SELL: "sell",
    VIEW_STRONG_SELL: "sell",
}


def view_side(view) -> str | None:
    """판정 라벨 → "buy" | "hold" | "sell". 판정 없음(None·데이터부족)은 None."""
    return _VIEW_SIDES.get(view)


@dataclass(frozen=True)
class Band:
    """수치 지표를 ±1 점으로 떨어뜨리는 구간 규칙.

    plus_below: 이 값보다 작으면 +1 (저평가·저PER 등)
    minus_at_or_above: 이 값 이상이면 -1
    minus_at_or_below: 이 값 이하면 -1 (적자 등)
    plus_at_or_above: 이 값 이상이면 +1 (고ROE 등)
    None 인 항목은 그 방향 판정을 하지 않는다.
    """
    plus_below: float | None = None
    minus_at_or_above: float | None = None
    minus_at_or_below: float | None = None
    minus_below: float | None = None
    plus_at_or_above: float | None = None
    skip_non_positive: bool = False  # 0·음수를 '판정 불가(0점)'로 둘지 (PBR 관례)

    def score(self, value) -> int:
        if value is None:
            return 0
        if self.skip_non_positive and value <= 0:
            return 0
        # 음수·0 을 별도 페널티로 잡는 규칙(PER<=0=적자, ROE<0=적자)을 먼저 본다.
        if self.minus_at_or_below is not None and value <= self.minus_at_or_below:
            return -1
        if self.minus_below is not None and value < self.minus_below:
            return -1
        if self.plus_below is not None and value < self.plus_below:
            return 1
        if self.minus_at_or_above is not None and value >= self.minus_at_or_above:
            return -1
        if self.plus_at_or_above is not None and value >= self.plus_at_or_above:
            return 1
        return 0


@dataclass(frozen=True)
class RuleSet:
    """판정 규칙 한 벌. 기본값은 현행 배포 규칙과 동일하다(BASELINE).

    평가 하네스(server/services/rule_eval.py)가 변형을 만들 때 이 dataclass 를 복제·수정해
    쓴다. 프로덕션 판정은 항상 BASELINE 을 사용한다.
    """
    id: str = "baseline"
    macd_scores: dict[str, int] = field(default_factory=lambda: {
        MACD_GOLDEN_CROSS: 2,
        MACD_ABOVE: 1,
        MACD_BELOW: -1,
        MACD_DEAD_CROSS: -2,
    })
    rsi_scores: dict[str, int] = field(default_factory=lambda: {
        RSI_OVERSOLD_ZONE: 1,
        RSI_OVERBOUGHT_ZONE: -1,
    })
    per_band: Band = field(default_factory=lambda: Band(
        minus_at_or_below=0, plus_below=10, minus_at_or_above=30
    ))
    pbr_band: Band = field(default_factory=lambda: Band(
        plus_below=1, minus_at_or_above=3, skip_non_positive=True
    ))
    roe_band: Band = field(default_factory=lambda: Band(
        plus_at_or_above=15, minus_below=0
    ))
    # 약(弱) 등급 경계: |score| >= weak_cutoff → 매수/매도
    weak_cutoff: int = 1
    # 강(强) 등급 경계: score >= short_strong / long_strong → 강력매수
    short_strong: int = 2
    long_strong: int = 3
    # 장기 판정에서 '강력' 등급에 기술 점수의 같은 방향 확증을 요구할지.
    #
    # 이 옵션이 False 였을 때의 결함: 재무 점수 최대치(±3)가 long_strong(3)과 같아서
    # PER<10 + PBR<1 + ROE>=15 만으로 기술 신호 없이 '강력매수'가 나왔다. 기술 지표가
    # 계산 불가(데이터부족)여도 0점=중립으로 취급되므로, 입력 절반이 결측인 상태에서
    # 최고 확신 등급이 나오는 것이었다. '종합 판정'이라는 이름과 모순된다.
    long_strong_requires_tech_confirm: bool = True

    def macd_score(self, label) -> int:
        return self.macd_scores.get(label, 0)

    def rsi_score(self, label) -> int:
        return self.rsi_scores.get(label, 0)

    def fundamental_score(self, per, pbr, roe) -> int:
        return (
            self.per_band.score(per)
            + self.pbr_band.score(pbr)
            + self.roe_band.score(roe)
        )

    def level5(self, score: int, strong: int, *, confirm: int | None = None) -> str:
        """점수 → 5단계 라벨.

        confirm 이 주어지면 '강력' 등급은 confirm 이 같은 방향으로 weak_cutoff 이상일 때만
        부여하고, 아니면 한 단계 낮춰 매수/매도로 둔다(위 long_strong_requires_tech_confirm).
        """
        weak = self.weak_cutoff
        if score >= strong:
            if confirm is None or confirm >= weak:
                return VIEW_STRONG_BUY
            return VIEW_BUY
        if score >= weak:
            return VIEW_BUY
        if score <= -strong:
            if confirm is None or confirm <= -weak:
                return VIEW_STRONG_SELL
            return VIEW_SELL
        if score <= -weak:
            return VIEW_SELL
        return VIEW_HOLD


BASELINE = RuleSet()


# ────────────────────────────────────────────
# 기여요인(팩터) 표시 메타데이터
#
# 프론트가 점수·설명문을 재계산하지 않도록, 백엔드가 화면에 필요한 것을 전부 만들어 보낸다.
# max_abs 는 기여 바 폭 계산용(그 팩터가 가질 수 있는 점수 절대값의 최댓값).
# ────────────────────────────────────────────

def _macd_rule_text(score: int) -> str:
    return {
        2: "골든크로스 — 강한 진입 (+2)",
        1: "MACD > 시그널 — 진입구간 (+1)",
        -1: "MACD < 시그널 — 매도구간 (−1)",
        -2: "데드크로스 — 강한 매도 (−2)",
    }.get(score, "판정 불가 (0)")


def _rsi_rule_text(score: int) -> str:
    if score > 0:
        return "과매도 — 반등 기대 (+1)"
    if score < 0:
        return "과매수 — 조정 주의 (−1)"
    return "30~70 중립 (0)"


def _per_rule_text(score: int) -> str:
    if score > 0:
        return "PER < 10 — 저평가 (+1)"
    if score < 0:
        return "PER ≥ 30·적자 — 부담 (−1)"
    return "보통 (0)"


def _pbr_rule_text(score: int) -> str:
    if score > 0:
        return "PBR < 1 — 자산 저평가 (+1)"
    if score < 0:
        return "PBR ≥ 3 — 고평가 (−1)"
    return "보통 (0)"


def _roe_rule_text(score: int) -> str:
    if score > 0:
        return "ROE ≥ 15% — 고수익성 (+1)"
    if score < 0:
        return "ROE < 0 — 적자 (−1)"
    return "보통 (0)"


RULE_TEXT = {
    "macd": _macd_rule_text,
    "rsi": _rsi_rule_text,
    "per": _per_rule_text,
    "pbr": _pbr_rule_text,
    "roe": _roe_rule_text,
}

MAX_ABS = {"macd": 2, "rsi": 1, "per": 1, "pbr": 1, "roe": 1}
