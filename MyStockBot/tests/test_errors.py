"""SQLite 쓰기 경합 → 429 변환.

## 예외를 위조하지 않는다
`sqlite3.OperationalError("database is locked")` 를 손으로 만들어 테스트하면
`sqlite_errorcode` 가 붙지 않아서(sqlite3 모듈이 실제 오류에서만 채운다) **분류 로직을
전혀 검증하지 못한다.** 그래서 여기서는 임시 DB에 진짜 쓰기 락을 걸고 그 예외 객체를
쓴다. 대조군(테이블 없음)도 같은 방식으로 실제 예외를 만든다.
"""
import asyncio
import sqlite3

import pytest
from starlette.requests import Request

from server import errors


def _real_exception(tmp_path, kind: str) -> sqlite3.OperationalError:
    """진짜 sqlite3 예외를 만들어 돌려준다(errorcode 가 채워진 객체)."""
    path = str(tmp_path / "probe.db")
    holder = sqlite3.connect(path)
    holder.execute("PRAGMA journal_mode=WAL")
    holder.execute("CREATE TABLE t (x)")
    holder.commit()
    # timeout=0 → busy_timeout 대기 없이 즉시 SQLITE_BUSY
    other = sqlite3.connect(path, timeout=0)
    try:
        if kind == "contention":
            holder.execute("BEGIN IMMEDIATE")
            holder.execute("INSERT INTO t VALUES (1)")
            with pytest.raises(sqlite3.OperationalError) as caught:
                other.execute("BEGIN IMMEDIATE")
        elif kind == "no_such_table":
            with pytest.raises(sqlite3.OperationalError) as caught:
                other.execute("SELECT * FROM definitely_not_here")
        else:  # pragma: no cover - 테스트 작성 실수 방어
            raise AssertionError(kind)
        return caught.value
    finally:
        other.close()
        holder.close()


def _request(path: str = "/api/paper/orders", method: str = "POST") -> Request:
    return Request({
        "type": "http", "http_version": "1.1", "method": method,
        "path": path, "raw_path": path.encode(), "query_string": b"secret=1",
        "headers": [], "scheme": "http", "server": ("test", 80), "client": ("t", 1),
        "root_path": "",
    })


# ── 분류 ──

def test_real_lock_is_classified_as_contention(tmp_path):
    exc = _real_exception(tmp_path, "contention")
    assert exc.sqlite_errorname == "SQLITE_BUSY", "실측 전제가 바뀌었다"
    assert errors.is_sqlite_contention(exc) is True


def test_real_non_lock_error_is_not_contention(tmp_path):
    """같은 OperationalError 라도 락이 아니면 429 로 바꾸면 안 된다."""
    exc = _real_exception(tmp_path, "no_such_table")
    assert exc.sqlite_errorname == "SQLITE_ERROR"
    assert errors.is_sqlite_contention(exc) is False


def test_message_lookalike_without_errorcode_is_not_contention():
    """문구가 같아도 errorcode 가 없으면 분류하지 않는다 — 문자열 매칭 금지의 회귀."""
    assert errors.is_sqlite_contention(
        sqlite3.OperationalError("database is locked")
    ) is False


@pytest.mark.parametrize("code, expected", [
    (sqlite3.SQLITE_BUSY, True),
    (sqlite3.SQLITE_LOCKED, True),
    # 확장 결과코드가 켜진 경우: 하위 8비트가 기본코드와 같다.
    (sqlite3.SQLITE_BUSY_SNAPSHOT, True),
    (sqlite3.SQLITE_LOCKED_SHAREDCACHE, True),
    (sqlite3.SQLITE_ERROR, False),
    (sqlite3.SQLITE_CORRUPT, False),
])
def test_code_classification(code, expected):
    exc = sqlite3.OperationalError("x")
    exc.sqlite_errorcode = code
    assert errors.is_sqlite_contention(exc) is expected


def test_extended_codes_low_byte_matches_primary():
    """마스킹 근거를 상수로 확인한다(추측이 아니라는 것을 고정)."""
    assert sqlite3.SQLITE_BUSY_SNAPSHOT & 0xFF == sqlite3.SQLITE_BUSY
    assert sqlite3.SQLITE_LOCKED_SHAREDCACHE & 0xFF == sqlite3.SQLITE_LOCKED


# ── 핸들러 ──

def test_contention_becomes_429_with_retry_after(tmp_path):
    exc = _real_exception(tmp_path, "contention")
    response = asyncio.run(
        errors.sqlite_operational_error_handler(_request(), exc)
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(errors.RETRY_AFTER_SECONDS)


def test_handler_response_leaks_nothing(tmp_path):
    """응답 본문에 예외 문구·DB 경로가 실리지 않는다 — 경로 노출 방지."""
    exc = _real_exception(tmp_path, "contention")
    response = asyncio.run(
        errors.sqlite_operational_error_handler(_request(), exc)
    )
    body = response.body.decode()
    assert "locked" not in body
    assert str(tmp_path) not in body
    assert ".db" not in body


def test_non_contention_is_reraised(tmp_path):
    """경합이 아니면 다시 던져 500 으로 남긴다 — 진짜 오류를 429 로 숨기지 않는다."""
    exc = _real_exception(tmp_path, "no_such_table")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(errors.sqlite_operational_error_handler(_request(), exc))


def test_query_string_is_not_logged(tmp_path, caplog):
    """쿼리스트링에 사용자 입력이 섞일 수 있으므로 경로만 남긴다."""
    import logging

    exc = _real_exception(tmp_path, "contention")
    with caplog.at_level(logging.WARNING):
        asyncio.run(errors.sqlite_operational_error_handler(_request(), exc))

    assert "/api/paper/orders" in caplog.text
    assert "secret=1" not in caplog.text


def test_handler_is_registered_on_the_app():
    """등록을 빼먹으면 위 테스트가 전부 통과하는데도 500 이 나간다."""
    from server.main import app

    assert app.exception_handlers.get(sqlite3.OperationalError) is (
        errors.sqlite_operational_error_handler
    )
