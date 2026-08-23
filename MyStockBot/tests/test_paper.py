"""모의투자 — 실제 SQLite 로 체결·평균단가·실현손익·마이그레이션을 검증한다.

## 이 파일이 생긴 이유
실현손익·체결가 출처를 추가하려고 코드를 열었을 때 **모의투자 경로에 테스트가 하나도
없었다.** 원자적 체결(BEGIN IMMEDIATE)·평균이동원가·시세 부재 시 매도 폴백이 전부
미검증이었다. 새 기능만 덮는 대신 기존 계약부터 함께 잠근다.

DB 는 목이 아니라 tmp_path 의 실제 파일이다 — 원자성·마이그레이션·SUM 집계는 목으로는
검증되지 않는다.
"""
import sqlite3
import threading

import pytest

import db as db_module


# config.PAPER_SEED_DEFAULT 와 같은 값으로 둔다 — server/services/paper.py 가 그 값을
# seed_default 로 넘기므로, 다르면 계좌 생성 시드와 조회 시드가 어긋난다.
SEED = 10_000_000.0


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "paper.db"))
    db_module.init_db()
    return db_module


def buy(db, code="005930", name="삼성전자", qty=10, price=70_000.0,
        source="market", status="open"):
    return db.execute_paper_order(code, name, "buy", qty, price, SEED,
                                  price_source=source, market_status=status)


def sell(db, code="005930", name="삼성전자", qty=10, price=80_000.0,
         source="market", status="open"):
    return db.execute_paper_order(code, name, "sell", qty, price, SEED,
                                  price_source=source, market_status=status)


def only_holding(account):
    assert len(account["holdings"]) == 1
    return account["holdings"][0]


# ── 기존 계약: 체결·평균단가 ──

def test_buy_updates_cash_and_holding(db):
    account = buy(db, qty=10, price=70_000.0)

    assert account["cash"] == SEED - 700_000
    h = only_holding(account)
    assert (h["code"], h["qty"], h["avg_cost"]) == ("005930", 10, 70_000.0)


def test_repeated_buys_use_weighted_average_cost(db):
    buy(db, qty=10, price=70_000.0)
    account = buy(db, qty=30, price=90_000.0)

    h = only_holding(account)
    assert h["qty"] == 40
    # (10*70000 + 30*90000) / 40 = 85000
    assert h["avg_cost"] == pytest.approx(85_000.0)


def test_partial_sell_keeps_average_cost(db):
    buy(db, qty=10, price=70_000.0)
    account = sell(db, qty=4, price=80_000.0)

    h = only_holding(account)
    assert h["qty"] == 6
    assert h["avg_cost"] == pytest.approx(70_000.0), "부분 매도가 평균단가를 바꿨다"


def test_full_sell_removes_the_holding(db):
    buy(db, qty=10, price=70_000.0)
    account = sell(db, qty=10, price=80_000.0)

    assert account["holdings"] == []
    assert account["cash"] == SEED - 700_000 + 800_000


def test_buy_beyond_cash_is_rejected_without_side_effects(db):
    with pytest.raises(db.InsufficientFundsError):
        buy(db, qty=1000, price=70_000.0)

    account = db.get_paper_account(SEED)
    assert account["cash"] == SEED
    assert account["holdings"] == []
    assert db.get_paper_trades() == [], "거부된 주문이 거래내역에 남았다"


def test_sell_beyond_holding_is_rejected_without_side_effects(db):
    buy(db, qty=5, price=70_000.0)
    cash_before = db.get_paper_account(SEED)["cash"]

    with pytest.raises(db.InsufficientFundsError):
        sell(db, qty=6, price=80_000.0)

    account = db.get_paper_account(SEED)
    assert account["cash"] == cash_before
    assert only_holding(account)["qty"] == 5


@pytest.mark.parametrize("qty", [0, -1])
def test_non_positive_qty_is_rejected(db, qty):
    with pytest.raises(db.InvalidOrderError):
        buy(db, qty=qty)


def test_non_positive_price_is_rejected(db):
    with pytest.raises(db.InvalidOrderError):
        buy(db, price=0.0)


# ── 체결가 출처 ──

def test_price_source_is_required(db):
    """기본값을 주면 호출부가 잊었을 때 조용히 'market' 으로 기록된다 — 그걸 막는다."""
    with pytest.raises(TypeError):
        db.execute_paper_order("005930", "삼성전자", "buy", 1, 70_000.0, SEED)


def test_unknown_price_source_is_rejected(db):
    with pytest.raises(db.InvalidOrderError):
        buy(db, source="아무거나")


def test_price_source_and_market_status_are_recorded(db):
    buy(db, source="market", status="open")
    sell(db, qty=10, price=70_000.0, source="book", status="closed")

    trades = db.get_paper_trades()
    by_side = {t["side"]: t for t in trades}
    assert by_side["buy"]["price_source"] == "market"
    assert by_side["buy"]["market_status"] == "open"
    assert by_side["sell"]["price_source"] == "book"
    assert by_side["sell"]["market_status"] == "closed"


# ── 실현손익 ──

def test_buy_records_no_realized_pnl(db):
    buy(db)
    assert db.get_paper_trades()[0]["realized_pnl"] is None


def test_sell_records_realized_pnl(db):
    buy(db, qty=10, price=70_000.0)
    sell(db, qty=4, price=80_000.0)

    trade = db.get_paper_trades()[0]
    assert trade["side"] == "sell"
    # (80000 - 70000) * 4
    assert trade["realized_pnl"] == pytest.approx(40_000.0)


def test_realized_pnl_can_be_negative(db):
    buy(db, qty=10, price=70_000.0)
    sell(db, qty=10, price=65_000.0)

    assert db.get_paper_trades()[0]["realized_pnl"] == pytest.approx(-50_000.0)


def test_realized_pnl_uses_average_cost_not_last_buy_price(db):
    """마지막 매수가로 계산하면 여기서 틀린다 — 평균이동원가여야 한다."""
    buy(db, qty=10, price=70_000.0)
    buy(db, qty=30, price=90_000.0)          # 평균 85,000
    sell(db, qty=40, price=90_000.0)

    # 평균단가 기준: (90000 - 85000) * 40 = 200,000
    # 마지막 매수가 기준이면 0 이 된다.
    assert db.get_paper_trades()[0]["realized_pnl"] == pytest.approx(200_000.0)


def test_account_accumulates_realized_pnl(db):
    buy(db, qty=10, price=70_000.0)
    sell(db, qty=5, price=80_000.0)          # +50,000
    sell(db, qty=5, price=60_000.0)          # -50,000

    assert db.get_paper_account(SEED)["realized_pnl"] == pytest.approx(0.0)


def test_book_price_sell_realizes_zero(db):
    """장부가 대체 체결은 체결가 == 평균단가라 실현손익이 0 이다.

    이 0 을 '손익 없음'으로 읽으면 안 되므로 price_source='book' 이 함께 남는다.
    """
    buy(db, qty=10, price=70_000.0)
    sell(db, qty=10, price=70_000.0, source="book")

    trade = db.get_paper_trades()[0]
    assert trade["realized_pnl"] == pytest.approx(0.0)
    assert trade["price_source"] == "book"


def test_reset_clears_realized_pnl(db):
    buy(db, qty=10, price=70_000.0)
    sell(db, qty=10, price=80_000.0)
    assert db.get_paper_account(SEED)["realized_pnl"] != 0

    account = db.reset_paper_account(SEED)

    assert account["realized_pnl"] == 0.0
    assert account["cash"] == SEED
    assert db.get_paper_trades() == []


# ── 항등식: 실현 + 미실현 == 총손익 ──

def test_realized_plus_unrealized_equals_total_pnl(db, monkeypatch):
    """수수료·세금이 없으므로 정확히 일치해야 한다(server/services/paper.py 유도 참고).

    깨지면 어느 쪽 계산이 틀렸다는 신호다.
    """
    from server.services import paper as paper_service

    orders = [
        ("buy", "005930", 10, 70_000.0),
        ("buy", "000660", 5, 120_000.0),
        ("buy", "005930", 30, 90_000.0),
        ("sell", "005930", 25, 95_000.0),
        ("sell", "000660", 5, 100_000.0),
        ("buy", "035720", 2, 45_000.0),
    ]
    for side, code, qty, price in orders:
        db.execute_paper_order(code, code, side, qty, price, SEED,
                               price_source="market", market_status="open")

    # 남은 보유의 현재가를 준다 → 미실현이 실제로 0 이 아닌 상황을 만든다.
    prices = {"005930": {"price": 99_000.0, "name": "삼성전자"},
              "035720": {"price": 40_000.0, "name": "카카오"}}
    monkeypatch.setattr(paper_service, "_price_map", lambda: prices)

    account = paper_service.get_account()

    assert account["priced_incomplete"] is False, "전 종목 현재가를 줬는데 미완성이다"
    assert account["realized_unknown_trades"] == 0
    assert account["realized_pnl"] + account["unrealized_pnl"] == pytest.approx(
        account["total_pnl"], abs=0.05
    )


def test_identity_holds_with_no_trades(db, monkeypatch):
    from server.services import paper as paper_service

    monkeypatch.setattr(paper_service, "_price_map", lambda: {})
    account = paper_service.get_account()

    assert (account["realized_pnl"], account["unrealized_pnl"]) == (0.0, 0.0)
    assert account["total_pnl"] == 0.0


# ── 마이그레이션: 사용자 데이터를 버리지 않는다 ──

def _legacy_trades_table(path: str) -> None:
    """새 컬럼이 없던 시절의 paper_trades 를 만들고 거래 1건을 넣는다."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now')),
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO paper_trades (code, name, side, qty, price, amount) "
        "VALUES ('005930', '삼성전자', 'sell', 3, 70000.0, 210000.0)"
    )
    conn.commit()
    conn.close()


def test_migration_adds_columns_and_keeps_rows(tmp_path, monkeypatch):
    """decision_alert_state 와 달리 DROP 하지 않는다 — 사용자의 거래 기록이다."""
    path = str(tmp_path / "legacy.db")
    _legacy_trades_table(path)
    monkeypatch.setattr(db_module, "DB_PATH", path)

    db_module.init_db()

    trades = db_module.get_paper_trades()
    assert len(trades) == 1, "기존 거래 기록이 사라졌다"
    row = trades[0]
    assert (row["code"], row["qty"], row["price"]) == ("005930", 3, 70_000.0)
    # 모르는 값을 안다고 적지 않는다.
    assert row["price_source"] is None
    assert row["market_status"] is None
    assert row["realized_pnl"] is None


def test_migration_is_idempotent(tmp_path, monkeypatch):
    path = str(tmp_path / "legacy.db")
    _legacy_trades_table(path)
    monkeypatch.setattr(db_module, "DB_PATH", path)

    db_module.init_db()
    db_module.init_db()          # 두 번째 부팅에서 ALTER 가 또 돌면 에러가 난다

    assert len(db_module.get_paper_trades()) == 1


def test_legacy_sells_are_counted_as_unknown(tmp_path, monkeypatch):
    """realized_pnl 이 NULL 인 매도는 0 으로 세지 않고 '모른다'로 노출한다."""
    path = str(tmp_path / "legacy.db")
    _legacy_trades_table(path)
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()

    account = db_module.get_paper_account(SEED)

    assert account["realized_unknown_trades"] == 1
    assert account["realized_pnl"] == 0.0, "NULL 을 0 으로 합산하는 건 맞다(SUM 제외)"


def test_new_sells_do_not_count_as_unknown(db):
    buy(db, qty=10, price=70_000.0)
    sell(db, qty=10, price=80_000.0)

    assert db.get_paper_account(SEED)["realized_unknown_trades"] == 0


# ── 원자성(문서화된 보증) ──

def test_concurrent_buys_never_overspend(db):
    """BEGIN IMMEDIATE 가 read-modify-write 를 직렬화한다 — 현금이 음수가 되면 안 된다.

    이 테스트만 시드를 작게 잡는다(90만원). 1주 30만원 × 8스레드 → 정확히 3주.
    """
    small_seed = 900_000.0
    db.reset_paper_account(small_seed)

    results = {"ok": 0, "rejected": 0, "other": []}
    lock = threading.Lock()

    def order():
        try:
            db.execute_paper_order("005930", "삼성전자", "buy", 1, 300_000.0, small_seed,
                                   price_source="market", market_status="open")
            outcome = "ok"
        except db.InsufficientFundsError:
            outcome = "rejected"
        except Exception as e:  # 락 경합이 예외로 새면 여기 잡힌다
            outcome = None
            with lock:
                results["other"].append(repr(e))
        if outcome:
            with lock:
                results[outcome] += 1

    threads = [threading.Thread(target=order) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert results["other"] == [], "예상 못한 예외가 났다"
    assert results["ok"] == 3, f"체결 수가 틀렸다: {results}"

    account = db.get_paper_account(small_seed)
    assert account["cash"] == pytest.approx(0.0)
    assert account["cash"] >= 0
    assert only_holding(account)["qty"] == 3
    assert len(db.get_paper_trades()) == 3, "거부된 주문이 거래내역에 남았다"


# ── 응답 스키마 ──

def test_account_matches_the_declared_schema(db, monkeypatch):
    from server.schemas import PaperAccountResponse, PaperTradesResponse
    from server.services import paper as paper_service

    buy(db, qty=10, price=70_000.0)
    sell(db, qty=4, price=80_000.0)
    monkeypatch.setattr(paper_service, "_price_map",
                        lambda: {"005930": {"price": 75_000.0, "name": "삼성전자"}})

    PaperAccountResponse.model_validate(paper_service.get_account())
    validated = PaperTradesResponse.model_validate(paper_service.get_trades())

    assert validated.items[0].realized_pnl == pytest.approx(40_000.0)
    assert validated.items[0].price_source == "market"
