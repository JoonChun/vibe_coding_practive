"""예외 → HTTP 응답 변환.

## 왜 필요한가
`db.py` 는 호출마다 새 연결을 열고 쓰기 경로는 `BEGIN IMMEDIATE` 로 직렬화한다
(`execute_paper_order` 등). 연결에 `PRAGMA busy_timeout=5000` 이 걸려 있으므로 대부분의
경합은 5초 안에 알아서 풀리지만, **5초를 넘기면 `sqlite3.OperationalError:
database is locked` 가 그대로 라우터 밖으로 나가 500** 이 된다.

500 은 두 가지를 잘못 말한다:
  · 클라이언트에게 — "서버가 깨졌다"(실제로는 잠시 붐빈 것이고, 재시도하면 된다)
  · 운영자에게 — 에러 로그에 서버 결함처럼 쌓인다
경합은 **일시적이고 재시도 가능한** 상태이므로 429 + `Retry-After` 가 맞다. 이 저장소는
이미 알림 테스트 발송의 동시 실행 제한에 같은 규약(429 + Retry-After)을 쓴다.

## 락을 어떻게 식별하나 — 문자열 매칭이 아니다
`sqlite3.OperationalError` 는 락 말고도 "no such table", "disk I/O error" 등을 함께
나른다. 메시지 문자열로 가르면 SQLite 버전이 문구를 바꾸는 순간 조용히 오분류된다.
대신 `sqlite3.Error.sqlite_errorcode`(Python 3.11+)를 본다. 실측으로 확인했다:

    BEGIN IMMEDIATE 경합 → OperationalError / sqlite_errorname='SQLITE_BUSY'  (code 5)
    SELECT * FROM nope  → OperationalError / sqlite_errorname='SQLITE_ERROR'

숫자는 하드코딩하지 않고 `sqlite3.SQLITE_BUSY`(5)·`sqlite3.SQLITE_LOCKED`(6) 상수를
쓴다. 확장 결과코드가 켜진 경우를 대비해 하위 8비트로 마스킹한다 — 확장코드의 하위
8비트가 기본코드와 같다는 것은 같은 모듈의 상수로 확인된다
(`SQLITE_BUSY_SNAPSHOT`=517 → 517 & 0xFF = 5, `SQLITE_LOCKED_SHAREDCACHE`=262 → 6).

`sqlite_errorcode` 가 없는 런타임(3.11 미만)에서는 **변환하지 않는다.** 문구 추측으로
분류하는 것보다 기존 동작(500)을 유지하는 편이 정직하다.
"""
import logging
import sqlite3

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# 경합으로 판단할 SQLite 기본 결과코드.
_CONTENTION_CODES = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED})

# 클라이언트에게 제시할 재시도 대기(초). busy_timeout(5초)을 이미 소진한 뒤이므로
# 곧바로 다시 때리면 같은 경합에 다시 걸린다.
RETRY_AFTER_SECONDS = 2


def is_sqlite_contention(exc: BaseException) -> bool:
    """이 예외가 "지금 붐빈다"인가(= 재시도하면 될 일). 아니면 진짜 오류."""
    code = getattr(exc, "sqlite_errorcode", None)
    if not isinstance(code, int):
        return False
    return (code & 0xFF) in _CONTENTION_CODES


async def sqlite_operational_error_handler(request: Request, exc: Exception):
    """경합이면 429, 그 밖의 OperationalError 는 다시 던져 500 으로 남긴다.

    핸들러가 예외를 다시 던지면 Starlette 의 ServerErrorMiddleware 가 받아 500 을
    만든다 — 즉 경합이 아닌 오류의 기존 동작이 그대로 보존된다.
    """
    if not is_sqlite_contention(exc):
        raise exc

    # 경로만 남긴다 — 쿼리스트링에 사용자 입력이 섞일 수 있다.
    logger.warning("[db] 경합으로 429 반환: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=429,
        content={"detail": "데이터베이스가 일시적으로 붐빕니다. 잠시 후 다시 시도하세요."},
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )
