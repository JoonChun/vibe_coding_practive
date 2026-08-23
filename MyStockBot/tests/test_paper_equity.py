"""모의투자 자산 추이 — 거래 이력 replay + 일봉 종가로 일자별 평가 재구성.

계좌 요약은 "지금 얼마"만 답한다. 이 곡선은 "언제부터 벌었나/잃었나"에 답하므로,
거래 사이의 가격 변동이 실제로 반영되는지가 핵심 계약이다(거래 시점만 잇는 계단식
근사면 그 질문에 답하지 못한다).

DB 는 목이 아니라 tmp_path 의 실제 파일이다 — 거래 replay·일봉 조인·평균단가 폴백은
목으로는 검증되지 않는다.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import db as db_module
from config import PAPER_SEED_DEFAULT
from server.services import paper

_KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "equity.db"))
    db_module.init_db()
    return db_module


def _kst_midnight(day: str) -> int:
    """'YYYY-MM-DD' → KST 자정 epoch(캔들 t 와 동일 규칙)."""
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=_KST).timestamp())


def _utc_ts(day: str, hour: int = 5) -> str:
    """KST 기준 그 날짜 장중(UTC 05:00 = KST 14:00)에 해당하는 UTC 저장 문자열."""
    dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=_KST, hour=hour + 9)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _seed_candles(db, code: str, closes: dict[str, float]):
    db.upsert_candles(code, "1d", [
        {"t": _kst_midnight(d), "open": c, "high": c, "low": c, "close": c, "volume": 100}
        for d, c in closes.items()
    ])


def _insert_trade(db, day: str, code: str, side: str, qty: int, price: float, name="삼성전자"):
    """execute_paper_order 는 '지금' 시각으로 기록하므로, 과거 날짜를 만들려면
    ts 를 직접 지정해 넣는다(테스트 전용 — 실제 코드 경로는 건드리지 않는다)."""
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO paper_trades (ts, code, name, side, qty, price, amount, "
            "price_source, market_status, realized_pnl) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (_utc_ts(day), code, name, side, qty, price, price * qty, "market", "open", None),
        )
        conn.commit()
    finally:
        conn.close()


def test_no_trades_returns_empty(db):
    result = paper.get_equity_curve()
    assert result["points"] == []
    assert result["notes"]


def test_seed_conserved_at_purchase_moment(db):
    """매수 직후 총자산은 시드 그대로여야 한다(현금이 주식으로 옮겨갔을 뿐)."""
    _seed_candles(db, "005930", {"2026-08-03": 70_000})
    _insert_trade(db, "2026-08-03", "005930", "buy", 10, 70_000)

    points = paper.get_equity_curve()["points"]
    assert points
    first = points[0]
    assert first["cash"] == PAPER_SEED_DEFAULT - 700_000
    assert first["holdings_value"] == 700_000
    assert first["total"] == PAPER_SEED_DEFAULT


def test_curve_reflects_price_moves_between_trades(db):
    """핵심 계약 — 거래가 없는 날에도 종가 변동이 곡선에 반영된다."""
    _seed_candles(db, "005930", {
        "2026-08-03": 70_000,
        "2026-08-04": 77_000,   # +10%
        "2026-08-05": 63_000,   # -10% (매수가 대비)
    })
    _insert_trade(db, "2026-08-03", "005930", "buy", 10, 70_000)

    points = paper.get_equity_curve()["points"]
    by_date = {p["date"]: p for p in points}
    assert by_date["2026-08-04"]["holdings_value"] == 770_000
    assert by_date["2026-08-05"]["holdings_value"] == 630_000
    # 현금은 그대로 — 거래가 없었으므로
    assert by_date["2026-08-04"]["cash"] == by_date["2026-08-05"]["cash"]
    assert by_date["2026-08-05"]["total"] == by_date["2026-08-05"]["cash"] + 630_000


def test_sell_moves_value_back_to_cash(db):
    _seed_candles(db, "005930", {
        "2026-08-03": 70_000,
        "2026-08-04": 80_000,
    })
    _insert_trade(db, "2026-08-03", "005930", "buy", 10, 70_000)
    _insert_trade(db, "2026-08-04", "005930", "sell", 10, 80_000)

    last = paper.get_equity_curve()["points"][-1]
    assert last["holdings_value"] == 0
    # 70만원에 사서 80만원에 판 뒤 — 시드 + 10만원
    assert last["cash"] == PAPER_SEED_DEFAULT + 100_000
    assert last["total"] == PAPER_SEED_DEFAULT + 100_000


def test_forward_fill_uses_prior_close_when_day_missing(db):
    """휴장일에는 그날 일봉이 없다 — 직전 종가로 이어붙이고 폴백 경고를 띄우지 않는다."""
    _seed_candles(db, "005930", {
        "2026-08-03": 70_000,
        # 2026-08-04 없음(휴장 가정)
        "2026-08-05": 72_000,
    })
    _insert_trade(db, "2026-08-04", "005930", "buy", 10, 70_000)  # 일봉 없는 날 거래

    result = paper.get_equity_curve()
    by_date = {p["date"]: p for p in result["points"]}
    # 거래일(08-04)은 직전 거래일 종가 70,000 으로 평가된다
    assert by_date["2026-08-04"]["holdings_value"] == 700_000
    assert not any("평균단가" in n for n in result["notes"])


def test_avg_cost_fallback_when_no_candles_at_all(db):
    """일봉이 아예 없는 신규 종목은 평균단가로 평가하고, 그 사실을 notes 로 알린다."""
    _insert_trade(db, "2026-08-03", "999999", "buy", 5, 10_000, name="신규종목")

    result = paper.get_equity_curve()
    assert result["points"][-1]["holdings_value"] == 50_000
    assert any("평균단가" in n for n in result["notes"])


def test_multiple_holdings_are_summed(db):
    _seed_candles(db, "005930", {"2026-08-03": 70_000, "2026-08-04": 71_000})
    _seed_candles(db, "000660", {"2026-08-03": 20_000, "2026-08-04": 25_000})
    _insert_trade(db, "2026-08-03", "005930", "buy", 10, 70_000)
    _insert_trade(db, "2026-08-03", "000660", "buy", 5, 20_000, name="SK하이닉스")

    last = paper.get_equity_curve()["points"][-1]
    assert last["holdings_value"] == 71_000 * 10 + 25_000 * 5


def test_points_are_date_sorted_and_unique(db):
    _seed_candles(db, "005930", {
        "2026-08-03": 70_000, "2026-08-04": 71_000, "2026-08-05": 72_000,
    })
    _insert_trade(db, "2026-08-03", "005930", "buy", 1, 70_000)
    _insert_trade(db, "2026-08-05", "005930", "buy", 1, 72_000)

    dates = [p["date"] for p in paper.get_equity_curve()["points"]]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))


def test_kst_date_boundary_after_market_close(db):
    """UTC 로 저장된 거래 시각이 KST 날짜로 올바르게 매핑된다 —
    한국 장 마감 후(UTC 오전)의 거래가 전날로 밀리면 안 된다."""
    _seed_candles(db, "005930", {"2026-08-03": 70_000})
    conn = db.get_connection()
    try:
        # UTC 2026-08-03 07:00 = KST 2026-08-03 16:00 (장 마감 후)
        conn.execute(
            "INSERT INTO paper_trades (ts, code, name, side, qty, price, amount, "
            "price_source, market_status, realized_pnl) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("2026-08-03 07:00:00", "005930", "삼성전자", "buy", 1, 70_000, 70_000,
             "market", "closed", None),
        )
        conn.commit()
    finally:
        conn.close()

    assert paper.get_equity_curve()["points"][0]["date"] == "2026-08-03"
