"""룰 평가 하네스 — 통계 유틸과 "결론을 내지 않는" 기본 동작 검증.

이 하네스의 가장 중요한 성질은 **정직하게 모르겠다고 말하는 것**이다. 검출력이 부족하거나
불일치쌍이 적을 때 "차이 발견"이라고 답하면 도구 자체가 해롭다. 그 게이트를 여기서 잠근다.
"""
import math

import decision_rules as rules
from server.services import rule_eval
from server.services.rule_eval import Observation, Series


# ── 통계 유틸 ──

def test_spearman_detects_monotonic_relationship():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert rule_eval.spearman(xs, [10.0, 20.0, 30.0, 40.0, 50.0]) == 1.0
    assert rule_eval.spearman(xs, [50.0, 40.0, 30.0, 20.0, 10.0]) == -1.0


def test_spearman_guards():
    assert rule_eval.spearman([1.0, 2.0], [1.0, 2.0]) is None       # 표본 부족
    assert rule_eval.spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # 분산 0
    assert rule_eval.spearman([1.0, 2.0, 3.0], [1.0, 2.0]) is None  # 길이 불일치


def test_spearman_handles_ties():
    rho = rule_eval.spearman([1.0, 1.0, 2.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0, 5.0])
    assert rho is not None and rho > 0.9


def test_mde_shrinks_as_sample_grows():
    small = rule_eval.minimum_detectable_effect(10)
    large = rule_eval.minimum_detectable_effect(1000)
    assert small > large
    # n=40 근방에서 두 비율 비교의 검출한계는 대략 20pp 수준 — 가중치 조정 효과(1~3pp)보다 크다.
    assert rule_eval.minimum_detectable_effect(40) > 10
    assert rule_eval.minimum_detectable_effect(0) is None


def test_cluster_sample_collapses_same_day_signals():
    """같은 날 여러 종목이 동시에 신호를 내면 독립 관측 N건이 아니라 1건이다."""
    same_day = [
        Observation(code=f"00000{i}", bar=10, cal_block=3, score=2, view="매수", fwd_pct=1.0)
        for i in range(30)
    ]
    assert rule_eval.cluster_sample(same_day) == 1

    spread = [
        Observation(code="005930", bar=i * 20, cal_block=i, score=2, view="매수", fwd_pct=1.0)
        for i in range(5)
    ]
    assert rule_eval.cluster_sample(spread) == 5


# ── 라벨 시계열 ──

def test_label_series_matches_pointwise_indicator_calls():
    """전 구간 1회 계산이 각 시점 prefix 계산과 같다는 전제(인과성)를 실측으로 확인."""
    import pandas as pd

    import indicators

    closes = [100 + math.sin(i / 5) * 10 + i * 0.05 for i in range(120)]
    macd_labels, rsi_labels = rule_eval.label_series(closes)

    for t in (60, 90, 119):
        df = pd.DataFrame({"close": closes[: t + 1]})
        assert macd_labels[t] == indicators.macd_cross_signal(df), f"t={t}"
        assert rsi_labels[t] == indicators.rsi_zone_signal(df), f"t={t}"


# ── 관측 생성 ──

def _series(code: str, n: int = 200, drift: float = 0.05) -> Series:
    closes = [100 + math.sin(i / 7) * 8 + i * drift for i in range(n)]
    return Series(code=code, closes=closes, day_index=list(range(n)))


def test_observe_respects_common_warmup():
    """warmup 을 공통 주입해야 변형끼리 같은 구간을 비교한다."""
    series = _series("005930")
    obs = rule_eval.observe(series, rules.BASELINE, horizon=20, warmup=35)

    assert obs
    assert min(o.bar for o in obs) >= 35
    assert max(o.bar for o in obs) < len(series.closes) - 20


def test_observe_score_equals_tech_only():
    """재무 과거값이 없으므로 점수는 기술 점수와 같아야 한다(재무 0점)."""
    obs = rule_eval.observe(_series("005930"), rules.BASELINE, horizon=20, warmup=35)
    for o in obs:
        assert -3 <= o.score <= 3


# ── evaluate ──

def test_evaluate_reports_base_rate_and_flags_fundamentals_untestable():
    panel = [_series("005930"), _series("035720", drift=0.02)]
    result = rule_eval.evaluate(panel, rules.BASELINE, horizon=20)

    assert result["observations"] > 0
    assert result["base_rate_pct"] is not None
    # 재무 가중치는 이 하네스로 검증 불가 — "차이 없음"으로 오독하지 않도록 명시.
    assert result["fundamentals_testable"] is False
    assert any("재무" in note for note in result["notes"])
    # 적중률은 base rate 대비 lift 로 제시된다.
    if result["buy"]["signals"] > 0:
        assert result["buy"]["lift_pp"] is not None


def test_evaluate_skips_short_history_and_reports_it():
    panel = [_series("005930"), Series(code="000660", closes=[100.0] * 30)]
    result = rule_eval.evaluate(panel, rules.BASELINE, horizon=20)

    assert "000660" in result["skipped_codes"]
    assert "000660" not in result["codes"]


def test_evaluate_empty_panel_is_safe():
    result = rule_eval.evaluate([], rules.BASELINE, horizon=20)
    assert result["observations"] == 0
    assert result["buy"]["signals"] == 0
    assert result["base_rate_pct"] is None


def test_time_in_market_and_turnover_present():
    result = rule_eval.evaluate([_series("005930")], rules.BASELINE, horizon=20)
    assert 0 <= result["time_in_market_pct"] <= 100
    assert result["turnover_per_year"] is not None


def test_always_buy_variant_is_fully_in_market():
    """비교군이 실제로 '항상 매수'로 동작하는지 — 상승장 재발견을 잡아내는 기준선이다."""
    always_buy = rules.RuleSet(id="always_buy_ish", weak_cutoff=-99, long_strong=-99)
    result = rule_eval.evaluate([_series("005930")], always_buy, horizon=20)
    assert result["time_in_market_pct"] == 100.0
    assert result["turnover_per_year"] == 0.0


# ── 결론을 내지 않는 게이트 ──

def test_compare_is_inconclusive_on_small_discordant_set():
    """불일치쌍이 적으면 어떤 차이도 결론이 아니다."""
    panel = [_series("005930")]
    base = rule_eval.evaluate(panel, rules.BASELINE, horizon=20)
    variant = rule_eval.evaluate(panel, rules.RuleSet(id="no_rsi", rsi_scores={}), horizon=20)

    result = rule_eval.compare(base, variant)

    assert result["verdict"] == "inconclusive"
    assert "검출한계" in result["verdict_reason"]
    assert result["discordant_pairs"] >= 0


def test_power_report_flags_underpowered_small_panel():
    """단일 종목 400봉 수준이면 반드시 underpowered 로 나와야 한다."""
    report = rule_eval.power_report([_series("005930", n=400)], horizon=20)

    assert report["verdict"] == "underpowered"
    assert report["mde_pp"] > 3.0
    assert "노이즈" in report["explanation"]


def test_power_report_on_empty_panel():
    report = rule_eval.power_report([], horizon=20)
    assert report["cluster_samples"] == 0
    assert report["mde_pp"] is None
    assert report["verdict"] == "underpowered"


def test_monotonicity_finds_no_signal_in_random_walk():
    """정보 없는 시계열에서는 점수↔수익 상관이 뚜렷하지 않아야 한다.

    난수를 쓰지 않고 결정적 톱니 시계열을 쓴다(테스트 재현성). 요구는 '상관이 정확히 0'이
    아니라 '|ρ| 이 1 근처가 아니다' — 우연히 강한 상관이 나오면 그건 도구가 패턴을
    만들어내고 있다는 신호다.
    """
    closes = [100 + (7 * i % 13) - 6 for i in range(300)]
    result = rule_eval.evaluate(
        [Series(code="005930", closes=[float(c) for c in closes],
                day_index=list(range(len(closes))))],
        rules.BASELINE, horizon=20,
    )
    rho = result["monotonicity"]["spearman_pooled"]
    if rho is not None:
        assert abs(rho) < 0.9, f"정보 없는 시계열에서 ρ={rho} — 도구가 패턴을 만들고 있다"


def test_monotonicity_bucket_table_marks_unreliable_buckets():
    result = rule_eval.evaluate([_series("005930")], rules.BASELINE, horizon=20)
    buckets = result["monotonicity"]["buckets"]

    assert buckets
    for row in buckets:
        assert set(row) == {"score", "n", "avg_forward_pct", "reliable"}
        assert row["reliable"] == (row["n"] >= rule_eval._MIN_BUCKET_SAMPLES)


def test_wilson_and_effective_sample_reuse_backtest_implementations():
    """같은 규칙을 두 번 구현하지 않았는지 — 하네스는 backtest 의 함수를 재사용한다."""
    from server.services import backtest

    assert rule_eval.wilson_interval(7, 10) == backtest._wilson_interval(7, 10)
    assert rule_eval.effective_sample([0, 20, 40], 20) == backtest._effective_sample(
        [0, 20, 40], 20
    )
