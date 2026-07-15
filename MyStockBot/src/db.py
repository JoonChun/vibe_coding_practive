import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH

# bar_history 에 저장되는 스냅샷 컬럼 (date, code 제외 — 별도 인자로 받음)
_BAR_ITEM_COLUMNS = [
    "name", "open", "close", "low", "high", "volume",
    "macd_1d", "rsi_1d", "macd_60m", "rsi_60m",
    "short_view", "long_view",
    "bb_upper", "bb_mid", "bb_lower",
    "per", "pbr", "roe", "revenue", "net_income",
    "source", "source_60m",
]


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
            CREATE TABLE IF NOT EXISTS bar_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                open REAL,
                close REAL,
                low REAL,
                high REAL,
                volume INTEGER,
                macd_1d TEXT,
                rsi_1d TEXT,
                macd_60m TEXT,
                rsi_60m TEXT,
                short_view TEXT,
                long_view TEXT,
                bb_upper REAL,
                bb_mid REAL,
                bb_lower REAL,
                per REAL,
                pbr REAL,
                roe REAL,
                revenue INTEGER,
                net_income INTEGER,
                source TEXT,
                source_60m TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(date, code)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bar_history_code ON bar_history(code, date DESC)"
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
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_bar_history(code, limit: int = 30) -> list[dict]:
    """종목의 bar_history 최근 limit건을 날짜 오름차순으로 반환.

    상세 판정 화면의 캔들 차트용. 데이터가 없으면 빈 리스트(404 아님).
    limit 은 1~120 사이로 강제한다. code 형식이 틀리면 ValueError.
    """
    normalized_code = _normalize_code(code)
    safe_limit = max(1, min(int(limit), 120))

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM bar_history "
            "WHERE code = ? ORDER BY date DESC LIMIT ?",
            (normalized_code, safe_limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
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


def save_daily_bars(date_str: str, items: list[dict]) -> int:
    if not items:
        return 0

    conn = get_connection()
    try:
        inserted = 0
        columns = ["date", "code"] + _BAR_ITEM_COLUMNS
        placeholders = ", ".join(["?"] * len(columns))
        sql = (
            f"INSERT OR IGNORE INTO bar_history ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
        for item in items:
            values = [date_str, item.get("code")] + [item.get(key) for key in _BAR_ITEM_COLUMNS]
            cursor = conn.execute(sql, values)
            inserted += cursor.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()
