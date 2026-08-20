import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH

# db 에 저장되는 fetched_at 등 UTC naive 타임스탬프 포맷 — SQLite datetime('now')와 동일 형식.
_UTC_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


class DuplicateError(Exception):
    """이미 활성 상태인 관심종목을 다시 추가하려 할 때 발생."""


def get_connection() -> sqlite3.Connection:
    data_dir = os.path.dirname(DB_PATH)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_master (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                market TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_master_name ON stock_master(name)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                code TEXT NOT NULL,
                tf TEXT NOT NULL,
                t INTEGER NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (code, tf, t)
            )
            """
        )
        # ── KRX 휴장일 캐시 ──
        # KIS 국내휴장일조회(CTCA0903R)는 "가급적 1일 1회 호출"을 요청하므로 결과를 여기
        # 영속 저장한다. in-memory 캐시만 쓰면 서버 재시작마다 재호출하게 된다.
        # is_open = opnd_yn(개장일여부) 을 0/1 로 저장.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_holidays (
                date TEXT PRIMARY KEY,
                is_open INTEGER NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )

        # ── 판정 전환 알림 기준선 ──
        # "직전 사이클과 비교"가 아니라 "마지막으로 **알린** 판정과 비교"한다.
        # in-memory 로만 들고 있으면 (1) 서버 재시작 때 기준선이 사라져 재부팅마다 전 종목
        # 알림이 터지고, (2) 판정이 A↔B 로 왕복할 때 매번 알림이 나간다. 영속화하면 둘 다
        # 공짜로 해결된다 — 왕복해서 돌아온 판정은 마지막 알린 값과 같으므로 알리지 않는다.
        #
        # fund_present / source 도 함께 저장한다: 재무데이터가 뒤늦게 도착하거나(장기 판정이
        # 재무 ±3점만큼 통째로 이동) 데이터 출처가 kis↔yfinance 로 바뀌면 판정이 바뀌는데,
        # 그건 시장이 아니라 **입력 구성**이 바뀐 것이라 알릴 사건이 아니다.
        #
        # notified_at 은 실제 발송 시각(쿨다운 기준), updated_at 은 행을 마지막으로 만진
        # 시각(TTL 재시딩 기준)이다. 무음 시딩은 notified_at 을 건드리지 않는다.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_alert_state (
                code TEXT NOT NULL,
                view_kind TEXT NOT NULL,
                view TEXT NOT NULL,
                fund_present INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                notified_at TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (code, view_kind)
            )
            """
        )

        # ── 모의투자(Paper Trading) ── 개인용 단일 계좌(id=1 싱글턴)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL NOT NULL,
                seed REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_holdings (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                qty INTEGER NOT NULL,
                avg_cost REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
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
            "CREATE INDEX IF NOT EXISTS idx_paper_trades_ts ON paper_trades(ts DESC)"
        )
        conn.commit()
    finally:
        conn.close()


def load_watchlist(include_inactive: bool = False) -> list[dict]:
    # stock_master 를 LEFT JOIN 해 market('KOSPI'|'KOSDAQ')을 함께 반환한다.
    # 마스터에 아직 없는 코드(갱신 전·상장폐지 등)는 market = NULL.
    conn = get_connection()
    try:
        base_select = (
            "SELECT w.id, w.code, w.name, w.is_active, w.created_at, sm.market AS market "
            "FROM watchlist w LEFT JOIN stock_master sm ON sm.code = w.code "
        )
        if include_inactive:
            rows = conn.execute(base_select + "ORDER BY w.id").fetchall()
        else:
            rows = conn.execute(
                base_select + "WHERE w.is_active = 1 ORDER BY w.id"
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _normalize_code(code) -> str:
    raw = str(code).strip()
    if not raw:
        raise ValueError(f"잘못된 종목코드 형식: {code}")
    normalized = raw.zfill(6).upper()
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError(f"잘못된 종목코드 형식: {code}")
    return normalized


def normalize_code(code) -> str:
    """종목코드 정규화(6자리 zero-padded 숫자)의 공개 인터페이스. 형식이 틀리면 ValueError."""
    return _normalize_code(code)


def add_watchlist_item(code, name) -> dict:
    normalized_code = _normalize_code(code)

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, code, name, is_active, created_at FROM watchlist WHERE code = ?",
            (normalized_code,),
        ).fetchone()

        if existing is not None:
            if existing["is_active"]:
                raise DuplicateError(f"이미 등록된 종목입니다: {normalized_code}")
            conn.execute(
                "UPDATE watchlist SET is_active = 1, name = ? WHERE code = ?",
                (name, normalized_code),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, code, name, is_active, created_at FROM watchlist WHERE code = ?",
                (normalized_code,),
            ).fetchone()
            return dict(row)

        conn.execute(
            "INSERT INTO watchlist (code, name) VALUES (?, ?)",
            (normalized_code, name),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, code, name, is_active, created_at FROM watchlist WHERE code = ?",
            (normalized_code,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def remove_watchlist_item(code) -> bool:
    normalized_code = _normalize_code(code)

    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE watchlist SET is_active = 0 WHERE code = ? AND is_active = 1",
            (normalized_code,),
        )
        # 알림 기준선도 같은 트랜잭션에서 지운다. 남겨두면 나중에 이 종목을 다시 추가했을 때
        # 그동안 시장이 움직인 결과가 '방금 전환'으로 알려진다(watchlist 는 soft delete 라
        # 행이 재사용되므로 기준선이 저절로 사라지지 않는다).
        conn.execute(
            "DELETE FROM decision_alert_state WHERE code = ?", (normalized_code,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def upsert_stock_master(rows: list[dict]) -> int:
    """[{code, name, market}, ...] 를 stock_master 에 upsert.

    executemany 한 번 + commit 한 번 = 트랜잭션 1개. 반영 건수 반환.
    """
    if not rows:
        return 0

    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stock_master (code, name, market, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            [(row["code"], row["name"], row["market"]) for row in rows],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_stock_master_meta() -> dict:
    """stock_master 건수와 가장 오래된 updated_at.

    startup/스케줄러에서 갱신 필요 여부(비어있음·7일 초과)를 판단하는 데 쓰인다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count, MIN(updated_at) AS oldest_updated_at FROM stock_master"
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def search_stocks(q: str, limit: int = 10) -> list[dict]:
    """종목마스터에서 코드/종목명으로 검색.

    매칭: 코드 정확일치, 코드 prefix, 이름 부분일치(이름 prefix 포함).
    정렬: 코드 정확일치 > 코드 prefix > 이름 prefix > 이름 contains.
    q 가 없거나 공백뿐이면 빈 리스트. limit 은 1~30 사이로 강제.
    마스터 테이블이 비어 있어도 예외 없이 빈 리스트를 반환한다.
    """
    query = (q or "").strip()
    if not query:
        return []

    safe_limit = max(1, min(int(limit), 30))

    # LIKE 와일드카드(%, _)를 이스케이프해 검색어 원문 그대로 매칭한다.
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    prefix_pattern = f"{escaped}%"
    contains_pattern = f"%{escaped}%"

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT code, name, market
            FROM stock_master
            WHERE code = :q
               OR code LIKE :prefix ESCAPE '\\'
               OR name LIKE :contains ESCAPE '\\'
            ORDER BY
                CASE
                    WHEN code = :q THEN 0
                    WHEN code LIKE :prefix ESCAPE '\\' THEN 1
                    WHEN name LIKE :prefix ESCAPE '\\' THEN 2
                    ELSE 3
                END,
                code
            LIMIT :limit
            """,
            {
                "q": query,
                "prefix": prefix_pattern,
                "contains": contains_pattern,
                "limit": safe_limit,
            },
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def upsert_candles(code: str, tf: str, items: list[dict]) -> int:
    """캔들 영속 저장소에 upsert. items 는 [{t, open, high, low, close, volume}, ...].

    단일 트랜잭션(executemany + commit 1회). (code, tf, t) PK 충돌 시 덮어쓴다
    (KIS/yfinance 재수집 시 동일 캔들이 갱신될 수 있으므로 REPLACE가 맞다).
    빈 items 는 no-op(0 반환) — 실패한 fetch 결과로 기존 데이터를 지우지 않기 위함.
    """
    if not items:
        return 0

    fetched_at = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT OR REPLACE INTO candles (code, tf, t, open, high, low, close, volume, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    code, tf, item.get("t"),
                    item.get("open"), item.get("high"), item.get("low"),
                    item.get("close"), item.get("volume"),
                    fetched_at,
                )
                for item in items
            ],
        )
        conn.commit()
        return len(items)
    finally:
        conn.close()


def get_candles_store(code: str, tf: str, limit: int) -> list[dict]:
    """(code, tf) 저장소에서 t 오름차순 마지막 limit개 반환. 데이터 없으면 빈 리스트."""
    safe_limit = max(1, int(limit))

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT t, open, high, low, close, volume FROM candles "
            "WHERE code = ? AND tf = ? ORDER BY t DESC LIMIT ?",
            (code, tf, safe_limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def get_candles_age_seconds(code: str, tf: str) -> float | None:
    """(code, tf) 저장소의 max(fetched_at) 로부터 현재(UTC)까지 경과 초. 데이터 없으면 None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MAX(fetched_at) AS fetched_at FROM candles WHERE code = ? AND tf = ?",
            (code, tf),
        ).fetchone()
        fetched_at = row["fetched_at"] if row else None
        if not fetched_at:
            return None
        try:
            fetched_dt = datetime.strptime(fetched_at, _UTC_TS_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        return (datetime.now(timezone.utc) - fetched_dt).total_seconds()
    finally:
        conn.close()


# ────────────────────────────────────────────
# KRX 휴장일 캐시 (KIS CTCA0903R 결과 영속화)
# ────────────────────────────────────────────

def upsert_market_holidays(rows: list[dict]) -> int:
    """[{date: 'YYYY-MM-DD', is_open: bool}, ...] 를 upsert. 단일 트랜잭션. 반영 건수 반환.

    빈 리스트는 no-op(0) — 실패한 조회 결과로 기존 캐시를 지우지 않기 위함이다.
    """
    if not rows:
        return 0

    fetched_at = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO market_holidays (date, is_open, fetched_at) VALUES (?, ?, ?)",
            [(r["date"], 1 if r["is_open"] else 0, fetched_at) for r in rows],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_market_open_flag(date_str: str) -> bool | None:
    """캐시된 개장일 여부. 해당 날짜가 캐시에 없으면 None(호출부가 하드코딩 표로 폴백)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT is_open FROM market_holidays WHERE date = ?", (date_str,)
        ).fetchone()
        return None if row is None else bool(row["is_open"])
    finally:
        conn.close()


def get_market_holiday_meta() -> dict:
    """휴장일 캐시 메타 — 건수·커버 범위·마지막 조회 시각.

    스케줄러가 "1일 1회" 제약을 지키며 갱신 필요 여부를 판단하는 데 쓴다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count, MIN(date) AS min_date, MAX(date) AS max_date, "
            "MAX(fetched_at) AS fetched_at FROM market_holidays"
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# ────────────────────────────────────────────
# 판정 전환 알림 기준선
# ────────────────────────────────────────────

def get_decision_alert_state() -> dict[tuple[str, str], dict]:
    """{(code, view_kind): {view, fund_present, source, notified_at, updated_at}}.

    사이클마다 종목 수만큼 SELECT 하지 않도록 전량을 한 번에 읽는다(관심종목 규모가
    수십 건이라 전량 읽기가 더 싸다).
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT code, view_kind, view, fund_present, source, notified_at, updated_at "
            "FROM decision_alert_state"
        ).fetchall()
        return {
            (r["code"], r["view_kind"]): {
                "view": r["view"],
                "fund_present": int(r["fund_present"]),
                "source": r["source"],
                "notified_at": r["notified_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        }
    finally:
        conn.close()


def upsert_decision_alert_state(rows: list[dict]) -> int:
    """[{code, view_kind, view, fund_present, source, notified: bool}, ...] 를 upsert.

    notified=False(무음 시딩)면 기존 notified_at 을 **보존한다** — 시딩이 쿨다운 기준
    시각을 뒤로 밀어 실제 전환 알림을 지연시키는 일이 없도록.
    """
    if not rows:
        return 0

    now = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO decision_alert_state
                (code, view_kind, view, fund_present, source, notified_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code, view_kind) DO UPDATE SET
                view = excluded.view,
                fund_present = excluded.fund_present,
                source = excluded.source,
                notified_at = COALESCE(excluded.notified_at, decision_alert_state.notified_at),
                updated_at = excluded.updated_at
            """,
            [
                (
                    r["code"], r["view_kind"], r["view"],
                    1 if r.get("fund_present") else 0,
                    r.get("source"),
                    now if r.get("notified") else None,
                    now,
                )
                for r in rows
            ],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def delete_decision_alert_state(code) -> int:
    """한 종목의 알림 기준선을 삭제. 관심종목에서 제거할 때 함께 지운다."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM decision_alert_state WHERE code = ?", (_normalize_code(code),)
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ────────────────────────────────────────────
# 모의투자(Paper Trading) — 개인용 단일 계좌(id=1)
# ────────────────────────────────────────────

class InvalidOrderError(Exception):
    """수량·가격이 유효하지 않은 주문."""


class InsufficientFundsError(Exception):
    """현금 잔액 부족(매수) 또는 보유 수량 부족(매도)."""


def _ensure_account(conn: sqlite3.Connection, seed: float) -> None:
    """계좌가 없으면 시드머니로 생성(멱등). 호출부에서 트랜잭션/커밋 관리."""
    conn.execute(
        "INSERT OR IGNORE INTO paper_account (id, cash, seed) VALUES (1, ?, ?)",
        (seed, seed),
    )


def _account_snapshot(conn: sqlite3.Connection) -> dict:
    acct = conn.execute(
        "SELECT cash, seed FROM paper_account WHERE id = 1"
    ).fetchone()
    holdings = conn.execute(
        "SELECT code, name, qty, avg_cost FROM paper_holdings WHERE qty > 0 ORDER BY code"
    ).fetchall()
    return {
        "cash": acct["cash"] if acct else 0.0,
        "seed": acct["seed"] if acct else 0.0,
        "holdings": [dict(h) for h in holdings],
    }


def get_paper_account(seed_default: float) -> dict:
    """가상 계좌 스냅샷(현금·시드·보유목록). 없으면 시드로 생성."""
    conn = get_connection()
    try:
        _ensure_account(conn, seed_default)
        conn.commit()
        return _account_snapshot(conn)
    finally:
        conn.close()


def get_paper_trades(limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit), 500))
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, ts, code, name, side, qty, price, amount "
            "FROM paper_trades ORDER BY id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def execute_paper_order(
    code, name: str, side: str, qty: int, price: float, seed_default: float
) -> dict:
    """시장가 즉시 체결 시뮬레이션. 잔액/보유 검증부터 갱신까지 단일 IMMEDIATE
    트랜잭션으로 원자화해 동시 주문 TOCTOU(초과매수·음수잔액·초과매도)를 방지한다.
    체결 성공 시 갱신된 계좌 스냅샷 반환.
    """
    normalized = _normalize_code(code)
    if side not in ("buy", "sell"):
        raise InvalidOrderError(f"잘못된 주문 유형: {side}")
    if not isinstance(qty, int) or qty <= 0:
        raise InvalidOrderError("수량은 1 이상의 정수여야 합니다.")
    price_f = float(price)
    if price_f <= 0:
        raise InvalidOrderError("체결 가격이 유효하지 않습니다.")

    amount = round(price_f * qty, 2)

    conn = get_connection()
    try:
        # BEGIN IMMEDIATE: 쓰기 락을 즉시 잡아 read-modify-write 를 직렬화
        conn.execute("BEGIN IMMEDIATE")
        _ensure_account(conn, seed_default)

        acct = conn.execute("SELECT cash FROM paper_account WHERE id = 1").fetchone()
        cash = acct["cash"]
        holding = conn.execute(
            "SELECT qty, avg_cost FROM paper_holdings WHERE code = ?", (normalized,)
        ).fetchone()

        if side == "buy":
            if amount > cash:
                raise InsufficientFundsError(
                    f"현금 잔액 부족: 필요 {amount:,.0f}원 / 보유 {cash:,.0f}원"
                )
            new_cash = cash - amount
            if holding is None:
                new_qty, new_avg = qty, price_f
            else:
                total_qty = holding["qty"] + qty
                new_avg = (holding["avg_cost"] * holding["qty"] + amount) / total_qty
                new_qty = total_qty
            conn.execute(
                "INSERT INTO paper_holdings (code, name, qty, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(code) DO UPDATE SET qty = ?, avg_cost = ?, name = ?, "
                "updated_at = datetime('now')",
                (normalized, name, new_qty, new_avg, new_qty, new_avg, name),
            )
        else:  # sell
            held = holding["qty"] if holding else 0
            if qty > held:
                raise InsufficientFundsError(
                    f"보유 수량 부족: 매도 {qty}주 / 보유 {held}주"
                )
            new_cash = cash + amount
            remaining = held - qty
            if remaining > 0:
                conn.execute(
                    "UPDATE paper_holdings SET qty = ?, updated_at = datetime('now') "
                    "WHERE code = ?",
                    (remaining, normalized),
                )
            else:
                conn.execute("DELETE FROM paper_holdings WHERE code = ?", (normalized,))

        conn.execute(
            "UPDATE paper_account SET cash = ?, updated_at = datetime('now') WHERE id = 1",
            (new_cash,),
        )
        conn.execute(
            "INSERT INTO paper_trades (code, name, side, qty, price, amount) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (normalized, name, side, qty, price_f, amount),
        )
        snapshot = _account_snapshot(conn)
        conn.commit()
        return snapshot
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_paper_account(seed: float) -> dict:
    """가상 계좌 초기화 — 보유·거래내역 삭제 후 현금을 시드로 리셋."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM paper_holdings")
        conn.execute("DELETE FROM paper_trades")
        conn.execute(
            "INSERT INTO paper_account (id, cash, seed, updated_at) "
            "VALUES (1, ?, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET cash = ?, seed = ?, updated_at = datetime('now')",
            (seed, seed, seed, seed),
        )
        snapshot = _account_snapshot(conn)
        conn.commit()
        return snapshot
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
