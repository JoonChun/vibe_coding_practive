import math

import pandas as pd
import pytest

from server.services import backtest


def test_sanitize_closes_forward_fill():
    out = backtest._sanitize_closes([0, None, 100, float("nan"), 110])
    assert all(x > 0 for x in out)
    assert out[0] == 100  # 선행 결측 back-fill
    assert out[3] == 100  # NaN → 직전 값


def test_sanitize_all_invalid_raises():
    with pytest.raises(ValueError):
        backtest._sanitize_closes([0, None, float("nan")])


def test_run_signal_backtest_basic():
    closes = [100 + math.sin(i / 6) * 8 + i * 0.1 for i in range(120)]
    df = pd.DataFrame({"t": [1600000000 + i * 86400 for i in range(120)], "close": closes})
    r = backtest.run_signal_backtest(df, 20)
    assert r["strategy_return_pct"] == r["strategy_return_pct"]  # not NaN
    assert {"buy", "sell", "curve", "strategy_return_pct"}.issubset(r)


def test_length_guard():
    with pytest.raises(ValueError):
        backtest.run_signal_backtest(pd.DataFrame({"close": [1, 2, 3]}), 20)


def test_zero_close_no_crash():
    closes = [100.0] * 120
    closes[50] = 0  # 거래정지 0원 봉
    df = pd.DataFrame({"close": closes})
    r = backtest.run_signal_backtest(df, 20)  # ZeroDivision 없이 통과해야 함
    assert r["strategy_return_pct"] == r["strategy_return_pct"]


# ── 표본 신뢰도 표기(정직성 보강) ──

def test_wilson_interval_brackets_point_estimate():
    lo, hi = backtest._wilson_interval(7, 10)
    assert 0 <= lo < 70 < hi <= 100
    # 표본이 커지면 구간이 좁아진다.
    lo2, hi2 = backtest._wilson_interval(700, 1000)
    assert (hi2 - lo2) < (hi - lo)


def test_wilson_interval_stays_in_bounds_at_extremes():
    assert backtest._wilson_interval(0, 5)[0] == 0.0
    assert backtest._wilson_interval(5, 5)[1] == 100.0
    assert backtest._wilson_interval(0, 0) is None


def test_effective_sample_discounts_clustered_signals():
    # 연속 20일치 신호는 같은 구간을 보므로 독립 관측 1건.
    assert backtest._effective_sample(list(range(20)), 20) == 1
    # 흩어져 있으면 그만큼 표본으로 인정한다.
    assert backtest._effective_sample([0, 20, 40, 60], 20) == 4
    # 경계: 정확히 horizon 만큼 떨어지면 독립으로 센다.
    assert backtest._effective_sample([0, 19], 20) == 1
    assert backtest._effective_sample([], 20) == 0


def test_result_exposes_sample_and_assumption_metadata():
    closes = [100 + math.sin(i / 6) * 8 + i * 0.1 for i in range(120)]
    df = pd.DataFrame({"t": [1600000000 + i * 86400 for i in range(120)], "close": closes})
    r = backtest.run_signal_backtest(df, 20)

    assert r["bars_used"] == 120
    assert r["bars_available"] == 120
    assert r["truncated"] is False
    assert r["fundamentals_included"] is False
    # 재무 미반영은 화면이 생략할 수 없도록 notes 로도 내려간다.
    assert any("재무" in note for note in r["notes"])
    assert "effective_signals" in r["buy"]
    assert "low_confidence" in r["buy"]


def test_truncation_is_disclosed():
    n = backtest._MAX_BARS + 150
    closes = [100 + math.sin(i / 6) * 8 for i in range(n)]
    df = pd.DataFrame({"t": [1600000000 + i * 86400 for i in range(n)], "close": closes})
    r = backtest.run_signal_backtest(df, 20)

    assert r["truncated"] is True
    assert r["bars_available"] == n
    assert r["bars_used"] == backtest._MAX_BARS
    assert any(str(backtest._MAX_BARS) in note for note in r["notes"])


def test_low_confidence_flag_and_ci_present_when_signals_exist():
    closes = [100 + math.sin(i / 6) * 8 + i * 0.1 for i in range(120)]
    df = pd.DataFrame({"close": closes})
    r = backtest.run_signal_backtest(df, 20)

    for side in ("buy", "sell"):
        s = r[side]
        if s["signals"] > 0:
            assert s["hit_rate_ci"] is not None
            assert s["hit_rate_ci"][0] <= s["hit_rate"] or s["low_confidence"]
            # 짧은 이력(120봉)에서는 독립 표본이 10건에 못 미쳐 참고치로 표시돼야 한다.
            assert s["low_confidence"] is True
