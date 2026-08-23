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


# ── 공유 카드(§15.2c) 계약 ────────────────────────────────────────────────
#
# 카드는 SNS 로 나가는 산출물이라 두 가지가 계약이다:
#   ① 화면에 그리는 필드가 응답에 **반드시** 있어야 한다 — 하나 빠지면 카드가 조용히
#      "—" 를 그린다. TS 타입은 백엔드가 필드를 지워도 알아채지 못한다(빌드 통과).
#   ② prd §15.2c 가 "카드에 명시 필수"로 못박은 가정·한계가 응답 `notes` 에 있어야
#      한다. caveat 문구를 프런트에 하드코딩하면 백엔드 계산과 갈라진다 — 실제로
#      `reinvest` 가 무시되는데 카드에는 "배당 재투자"만 적히는 사고가 이 경로다.

def _fake_series(monkeypatch, n=120):
    """네트워크 없이 dca_backtest 를 통과시킨다 — 월봉 n개를 우상향으로."""
    items = _items(n)
    monkeypatch.setattr(dca, "_long_series", lambda code, tf, want: (items, "test", False))
    return items


# 카드가 실제로 그리는 필드 전부.
_CARD_FIELDS = (
    "return_pct", "principal", "eval_value", "profit",
    "buys", "avg_price", "current_price", "total_shares",
    "start_date", "end_date", "freq", "mode", "per", "notes", "curve",
)


def test_card_fields_present(monkeypatch):
    _fake_series(monkeypatch)
    r = dca.dca_backtest("005930", months=120)
    missing = [k for k in _CARD_FIELDS if k not in r]
    assert missing == [], f"공유 카드가 그리는 필드가 빠졌다: {missing}"
    assert r["avg_price"] is not None
    assert r["start_date"] and r["end_date"]


def test_notes_always_state_dividends_excluded(monkeypatch):
    """배당 제외(가격 수익만)는 reinvest 를 안 켰을 때도 카드에 있어야 한다.

    켰을 때만 고지하면, 기본값(off)으로 공유된 카드는 "이 수익률에 배당이 들어갔나"에
    답하지 않는다. 히어로 수익률이 단독으로 퍼지는 포맷이라 이게 곧 오해가 된다.
    """
    _fake_series(monkeypatch)
    notes = dca.dca_backtest("005930", reinvest=False)["notes"]
    assert any("배당" in n for n in notes), notes


def test_notes_state_start_date_sensitivity(monkeypatch):
    """prd §15.2c: "시작 시점 민감" 은 카드 명시 필수 항목이다."""
    _fake_series(monkeypatch)
    notes = dca.dca_backtest("005930")["notes"]
    assert any("시작" in n for n in notes), notes


def test_reinvest_requested_but_unsupported_is_still_called_out(monkeypatch):
    """배당 제외 고지가 상시화되어도, '요청했는데 반영 안 됨' 고지는 따로 남아야 한다.

    두 문장은 다른 것을 말한다: 하나는 숫자의 정의, 하나는 사용자의 입력이 무시됐다는
    사실이다. 후자를 지우면 체크박스가 조용히 아무것도 안 하는 UI 가 된다.
    """
    _fake_series(monkeypatch)
    notes = dca.dca_backtest("005930", reinvest=True)["notes"]
    assert any("미지원" in n or "반영되지" in n for n in notes), notes


def test_notes_have_no_duplicates(monkeypatch):
    _fake_series(monkeypatch)
    notes = dca.dca_backtest("005930", freq="quarterly", reinvest=True)["notes"]
    assert len(notes) == len(set(notes)), notes
