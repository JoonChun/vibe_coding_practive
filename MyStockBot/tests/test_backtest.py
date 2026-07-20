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
