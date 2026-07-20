import pytest

from server.services import dca


def _items(n, start=100):
    return [{"t": 1600000000 + i * 2600000, "close": start + i} for i in range(n)]


def test_run_dca_qty():
    r = dca.run_dca_backtest(_items(24), "qty", 1)
    assert r["buys"] == 24
    assert r["total_shares"] == 24
    assert r["principal"] > 0
    assert r["curve"][-1]["value"] >= r["curve"][-1]["principal"]  # 우상향 데이터


def test_run_dca_amount_principal():
    r = dca.run_dca_backtest(_items(12), "amount", 100000)
    assert r["principal"] == round(100000 * 12)
    assert r["total_shares"] > 0


def test_run_dca_insufficient():
    with pytest.raises(dca.InsufficientHistoryError):
        dca.run_dca_backtest([{"t": 1, "close": 100}])


def test_run_dca_bad_mode():
    with pytest.raises(ValueError):
        dca.run_dca_backtest(_items(3), "bad")


def test_chunk_last():
    items = [{"t": i, "close": i} for i in range(9)]
    q = dca._chunk_last(items, 3)
    assert [x["t"] for x in q] == [2, 5, 8]
