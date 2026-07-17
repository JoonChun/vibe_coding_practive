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

    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, _API_TOKEN):
        return JSONResponse(
            status_code=401,
            content={"detail": "인증이 필요합니다"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)
