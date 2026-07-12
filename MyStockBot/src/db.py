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
        conn.commit()
    finally:
        conn.close()


def load_watchlist(include_inactive: bool = False) -> list[dict]:
    conn = get_connection()
    try:
        if include_inactive:
            rows = conn.execute(
                "SELECT id, code, name, is_active, created_at FROM watchlist ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, code, name, is_active, created_at FROM watchlist "
                "WHERE is_active = 1 ORDER BY id"
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
