"""API 토큰 인증 미들웨어.

MYSTOCKBOT_API_TOKEN 환경변수가 설정되어 있으면 모든 /api/* 요청에
"Authorization: Bearer <토큰>" 헤더를 요구한다. 설정되어 있지 않으면
인증은 비활성화된다 (로컬 개발 편의).

예외:
  - OPTIONS 메서드 (CORS preflight) — 항상 통과
  - GET /api/health — 도커 헬스체크·연결 확인용, 항상 무인증
  - /api 로 시작하지 않는 경로 (/docs, /openapi.json 등) — 통과
    (개인용 배포라 문서는 열어두되, 실제 /api 호출은 어차피 401)
"""
import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from config import API_TOKEN_ENV_KEY

# 요청마다 os.environ 을 다시 읽지 않도록 모듈 로드(=앱 시작) 시 1회만 읽는다.
_API_TOKEN = os.environ.get(API_TOKEN_ENV_KEY, "").strip() or None

_HEALTH_PATH = "/api/health"
_API_PREFIX = "/api"


def is_auth_enabled() -> bool:
    """API 토큰 인증이 활성화되어 있는지 여부."""
    return _API_TOKEN is not None


def tokens_match(given: str, expected: str) -> bool:
    """상수시간 토큰 비교. **바이트로 비교한다.**

    `secrets.compare_digest` 는 `str` 을 받으면 **비ASCII 문자에서 TypeError 를 던진다**
    (실측: `compare_digest('여기에_토큰', 'x')` → TypeError). 미들웨어에서 그 예외가
    새면 틀린 토큰이 401 이 아니라 **500** 으로 나간다 — 실제로 사용자가 안내 문서의
    플레이스홀더를 그대로 보내 500 을 받았고, "서버가 고장났다"로 읽혔다. 설정한 토큰
    자체가 비ASCII 면 **모든 인증 요청이 500** 이 되어 인증을 켜는 순간 서버를 못 쓴다.

    UTF-8 바이트로 인코딩해 비교하면 어떤 문자든 안전하고 상수시간 성질도 유지된다
    (길이가 다르면 compare_digest 가 길이를 누설하는 것은 문서화된 성질이고, 토큰
    길이 누설은 이 앱에서 감수할 수 있는 수준이다).

    surrogate 가 섞인 값(잘못 디코딩된 헤더)도 인코딩이 실패할 수 있으므로 방어한다.
    """
    try:
        return secrets.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))
    except (UnicodeEncodeError, ValueError):
        return False


def _is_exempt(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    path = request.url.path
    if path == _HEALTH_PATH:
        return True
    if not path.startswith(_API_PREFIX):
        return True
    return False


async def auth_middleware(request: Request, call_next):
    if _API_TOKEN is None or _is_exempt(request):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")

    if scheme.lower() != "bearer" or not token or not tokens_match(token, _API_TOKEN):
        return JSONResponse(
            status_code=401,
            content={"detail": "인증이 필요합니다"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)
