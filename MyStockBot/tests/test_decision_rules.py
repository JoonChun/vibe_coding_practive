"""판정 엔진 진리표 잠금 테스트.

기존에는 판정 결과를 단정하는 테스트가 사실상 하나(test_db_and_indicators.py 의 방향성
검사)뿐이었고, 극단값만 넣어 어떤 규칙 변경에도 그냥 통과했다 — 결함도 못 잡고 회귀도
못 막는 상태였다. 여기서 (기술점수 × 재무점수) 49칸 전체를 고정한다.

특히 다음 두 성질을 명시적으로 잠근다:
  1) '강력' 등급은 기술 점수의 같은 방향 확증을 요구한다 (재무만으로 최고 등급 불가)
  2) 기술 지표가 결측일 때 그것을 '중립 확증'으로 오독하지 않는다
"""
import pytest

import decision_rules as rules
import indicators

# 각 기술 점수를 만들어내는 (macd 라벨, rsi 라벨) 조합.
# tech = macd_score + rsi_score, 범위 -3..+3.
_TECH_INPUTS = {
    3: (rules.MACD_GOLDEN_CROSS, rules.RSI_OVERSOLD_ZONE),    # +2 +1
    2: (rules.MACD_GOLDEN_CROSS, rules.RSI_NEUTRAL),          # +2  0
    1: (rules.MACD_ABOVE, rules.RSI_NEUTRAL),                 # +1  0
    0: (rules.MACD_ABOVE, rules.RSI_OVERBOUGHT_ZONE),         # +1 -1
    -1: (rules.MACD_BELOW, rules.RSI_NEUTRAL),                # -1  0
    -2: (rules.MACD_DEAD_CROSS, rules.RSI_NEUTRAL),           # -2  0
    -3: (rules.MACD_DEAD_CROSS, rules.RSI_OVERBOUGHT_ZONE),   # -2 -1
}

# 각 재무 점수를 만들어내는 (per, pbr, roe).
_FUND_INPUTS = {
    3: (8.0, 0.6, 18.0),      # +1 +1 +1
    2: (8.0, 0.6, 5.0),       # +1 +1  0
    1: (8.0, 1.5, 5.0),       # +1  0  0
    0: (15.0, 1.5, 5.0),      # 0  0  0
    -1: (35.0, 1.5, 5.0),     # -1  0  0
    -2: (35.0, 4.0, 5.0),     # -1 -1  0
    -3: (35.0, 4.0, -2.0),    # -1 -1 -1
}


def test_tech_inputs_produce_expected_scores():
    """진리표의 전제(입력 조합 → 의도한 점수)가 실제로 성립하는지 먼저 확인한다."""
    for expected, (macd, rsi) in _TECH_INPUTS.items():
        assert rules.BASELINE.macd_score(macd) + rules.BASELINE.rsi_score(rsi) == expected


def test_fund_inputs_produce_expected_scores():
    for expected, (per, pbr, roe) in _FUND_INPUTS.items():
        assert rules.BASELINE.fundamental_score(per, pbr, roe) == expected


def _long_view(tech: int, fund: int) -> str:
    macd, rsi = _TECH_INPUTS[tech]
    per, pbr, roe = _FUND_INPUTS[fund]
    return indicators.long_term_view(macd, rsi, per, pbr, roe)


# tech(행 -3..+3) × fund(열 -3..+3) 장기 판정 진리표.
# 강력 등급은 합계가 ±3 을 넘고 **동시에** 기술 점수가 같은 방향으로 ±1 이상일 때만.
_EXPECTED_LONG = {
    #  tech: {fund: view}
    3: {-3: "관망", -2: "매수", -1: "매수", 0: "강력매수", 1: "강력매수", 2: "강력매수", 3: "강력매수"},
    2: {-3: "매도", -2: "관망", -1: "매수", 0: "매수", 1: "강력매수", 2: "강력매수", 3: "강력매수"},
    1: {-3: "매도", -2: "매도", -1: "관망", 0: "매수", 1: "매수", 2: "강력매수", 3: "강력매수"},
    0: {-3: "매도", -2: "매도", -1: "매도", 0: "관망", 1: "매수", 2: "매수", 3: "매수"},
    -1: {-3: "강력매도", -2: "강력매도", -1: "매도", 0: "매도", 1: "관망", 2: "매수", 3: "매수"},
    -2: {-3: "강력매도", -2: "강력매도", -1: "강력매도", 0: "매도", 1: "매도", 2: "관망", 3: "매수"},
    -3: {-3: "강력매도", -2: "강력매도", -1: "강력매도", 0: "강력매도", 1: "매도", 2: "매도", 3: "관망"},
}


@pytest.mark.parametrize("tech", sorted(_EXPECTED_LONG))
def test_long_term_view_truth_table(tech):
    for fund, expected in _EXPECTED_LONG[tech].items():
        assert _long_view(tech, fund) == expected, f"tech={tech} fund={fund}"


def test_fundamentals_alone_cannot_reach_strong_grade():
    """핵심 결함 회귀 방지 — 기술 신호 없이 재무만으로 최고/최저 등급이 나오면 안 된다.

    PER 8배·PBR 0.6·ROE 18% (재무 +3) 인데 일봉 MACD 는 매도구간(-1), RSI 는 과매도(+1)로
    기술 점수 0 → 예전에는 합계 +3 으로 '강력매수'가 나왔다. 기술적으로는 하락 추세인데
    최고 확신 등급이 붙던 셀이다.
    """
    assert _long_view(0, 3) == "매수"
    # 대칭: 재무 -3 + 기술 0 도 강력매도가 아니어야 한다(게이지 5구간 대칭성 유지).
    assert _long_view(0, -3) == "매도"


def test_missing_technicals_are_not_read_as_confirmation():
    """기술 지표가 결측(None·'데이터부족')이면 그것을 '중립 확증'으로 취급하지 않는다."""
    per, pbr, roe = _FUND_INPUTS[3]
    for missing in (None, rules.NO_DATA):
        assert indicators.long_term_view(missing, missing, per, pbr, roe) == "매수"

    per, pbr, roe = _FUND_INPUTS[-3]
    for missing in (None, rules.NO_DATA):
        assert indicators.long_term_view(missing, missing, per, pbr, roe) == "매도"


def test_no_data_when_everything_missing():
    assert indicators.long_term_view(None, None, None, None, None) == rules.NO_DATA
    assert indicators.short_term_view(None, None) == rules.NO_DATA
    assert indicators.long_term_score(None, None, None, None, None) is None
    assert indicators.short_term_score(None, None) is None


def test_offsetting_fundamentals_still_report_no_data():
    """재무가 실재하지만 상쇄되어 fund==0 이고 기술이 결측이면 '데이터부족'.

    현행 게이트(`macd/rsi 결측 and fund == 0`)의 의도된 성질이다. 이 셀의 동작을 바꾸려면
    의식적으로 바꿔야 하므로 여기 고정해 둔다.
    """
    # PER 15(0점) + PBR 1.5(0점) + ROE 5(0점) → fund 0
    assert indicators.long_term_view(None, None, 15.0, 1.5, 5.0) == rules.NO_DATA
    # PER 5(+1) + PBR 4(-1) → 상쇄되어 fund 0
    assert indicators.long_term_view(None, None, 5.0, 4.0, 5.0) == rules.NO_DATA


# ── 단기 판정: 기술 점수만이므로 확증 요구가 자동 충족된다 ──

_EXPECTED_SHORT = {3: "강력매수", 2: "강력매수", 1: "매수", 0: "관망",
                   -1: "매도", -2: "강력매도", -3: "강력매도"}


@pytest.mark.parametrize("tech,expected", sorted(_EXPECTED_SHORT.items()))
def test_short_term_view_truth_table(tech, expected):
    macd, rsi = _TECH_INPUTS[tech]
    assert indicators.short_term_view(macd, rsi) == expected


def test_short_term_view_unaffected_by_confirm_rule():
    """단기 판정은 이번 변경(강력 등급 확증 요구)의 영향을 받지 않아야 한다.

    단기 점수 = 기술 점수이므로 score >= strong 이면 tech >= strong >= weak 가 항상 성립한다.
    """
    strict = rules.RuleSet(long_strong_requires_tech_confirm=True)
    loose = rules.RuleSet(long_strong_requires_tech_confirm=False)
    for tech, (macd, rsi) in _TECH_INPUTS.items():
        assert (
            indicators.short_term_view(macd, rsi, ruleset=strict)
            == indicators.short_term_view(macd, rsi, ruleset=loose)
        ), f"tech={tech}"


# ── 점수와 판정의 일관성 (long_view / long_score 는 같은 규칙의 두 표현) ──

def test_score_and_view_stay_consistent():
    """long_score 로 판정을 재구성했을 때 long_view 와 어긋나면 API 응답이 자기모순이 된다."""
    for tech, (macd, rsi) in _TECH_INPUTS.items():
        for fund, (per, pbr, roe) in _FUND_INPUTS.items():
            score = indicators.long_term_score(macd, rsi, per, pbr, roe)
            view = indicators.long_term_view(macd, rsi, per, pbr, roe)
            assert score == tech + fund, f"tech={tech} fund={fund}"
            # 판정이 매수 계열이면 점수도 양수여야 한다(그 역은 확증 규칙 때문에 성립 안 함).
            if view in (rules.VIEW_STRONG_BUY, rules.VIEW_BUY):
                assert score >= rules.BASELINE.weak_cutoff
            if view in (rules.VIEW_STRONG_SELL, rules.VIEW_SELL):
                assert score <= -rules.BASELINE.weak_cutoff


# ── 밴드 경계값 ──

@pytest.mark.parametrize("per,expected", [
    (-5.0, -1), (0.0, -1),        # 적자
    (9.99, 1), (10.0, 0),          # 저평가 경계
    (29.99, 0), (30.0, -1),        # 고평가 경계
    (None, 0),
])
def test_per_band_boundaries(per, expected):
    assert rules.BASELINE.per_band.score(per) == expected


@pytest.mark.parametrize("pbr,expected", [
    (0.0, 0), (-1.0, 0),           # 0·음수는 판정 불가(0점)
    (0.99, 1), (1.0, 0),
    (2.99, 0), (3.0, -1),
    (None, 0),
])
def test_pbr_band_boundaries(pbr, expected):
    assert rules.BASELINE.pbr_band.score(pbr) == expected


@pytest.mark.parametrize("roe,expected", [
    (-0.01, -1), (0.0, 0),
    (14.99, 0), (15.0, 1),
    (None, 0),
])
def test_roe_band_boundaries(roe, expected):
    assert rules.BASELINE.roe_band.score(roe) == expected


def test_unknown_labels_score_zero():
    """미등록 라벨·None 은 0점. (점수표 lookup 이 .get(label, 0) 이라는 성질 고정)"""
    assert rules.BASELINE.macd_score("존재하지않는라벨") == 0
    assert rules.BASELINE.macd_score(None) == 0
    assert rules.BASELINE.rsi_score(rules.RSI_NEUTRAL) == 0
    assert rules.BASELINE.rsi_score(rules.NO_DATA) == 0
