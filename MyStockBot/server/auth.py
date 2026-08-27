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
import threading
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse

from config import API_TOKEN_ENV_KEY

# 요청마다 os.environ 을 다시 읽지 않도록 모듈 로드(=앱 시작) 시 1회만 읽는다.
_API_TOKEN = os.environ.get(API_TOKEN_ENV_KEY, "").strip() or None

_HEALTH_PATH = "/api/health"
_API_PREFIX = "/api"

# ── 인증 실패 감속기(브루트포스 방어) ──
#
# IP별 추적은 하지 않는다 — 터널(cloudflared/Tailscale) 뒤에서는 모든 요청의
# client IP 가 터널 프로세스의 로컬 주소로 보여 IP별 구분이 무의미하다.
# 대신 **토큰을 제시한 실패만** 전역으로 센다.
#
# ★ 이 장치는 사용자를 잠그지 않는다 — 실패 응답은 임계를 넘든 말든 **항상 401** 이고,
#   감속은 Retry-After 헤더로만 알린다. 예전에는 임계 초과 시 429 를 줬는데, 그러면
#   프론트가 401 을 못 받아 토큰 입력 배너가 뜨지 않아 **사용자가 토큰을 넣을 방법을
#   잃었다**(실측 확인). 첫 접속은 폴링 3종이 동시에 401 을 받으므로 임계를 금방 넘는다.
#
# ★ Authorization 헤더가 없는 요청은 카운트하지 않는다 — 값을 찍어보는 공격이 아니라
#   "아직 토큰을 입력하지 않은 정상 첫 접속"이다.
_FAIL_WINDOW_SECONDS = 60
_FAIL_THRESHOLD = 10
_RETRY_AFTER_SECONDS = 60
_fail_times: deque = deque()
_fail_lock = threading.Lock()


def _register_failure_and_check_limit() -> bool:
    """인증 실패 1건을 기록하고, 창(_FAIL_WINDOW_SECONDS) 안의 실패 수가 임계치를
    넘었으면 True(=이 응답에 Retry-After 를 붙일 대상)를 돌려준다.
    상태코드는 어느 쪽이든 401 이다 — 위 주석 참조."""
    now = time.monotonic()
    with _fail_lock:
        while _fail_times and now - _fail_times[0] > _FAIL_WINDOW_SECONDS:
            _fail_times.popleft()
        _fail_times.append(now)
        return len(_fail_times) > _FAIL_THRESHOLD


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
    presented = scheme.lower() == "bearer" and bool(token)

    # 유효한 토큰은 감속 상태와 무관하게 항상 통과한다.
    if presented and tokens_match(token, _API_TOKEN):
        return await call_next(request)

    # ── 실패 경로 ──
    # ★ 상태코드는 **항상 401** 이다. 예전에는 감속 임계를 넘으면 429 를 줬는데, 그러면
    #   프론트가 401 을 못 받아 **토큰 입력 배너 자체가 안 뜬다**(useSnapshot.errorStatus
    #   === 401 로 판정한다). 즉 사용자가 토큰을 넣을 UI 를 잃는다 — 실측으로 확인한
    #   결함이다. 첫 접속은 폴링 3종이 동시에 401 을 받으므로 임계를 금방 넘는다.
    #   감속은 상태코드가 아니라 Retry-After 로만 알린다.
    #
    # ★ 카운트는 **토큰을 제시한 실패만** 센다. Authorization 헤더가 아예 없는 요청은
    #   "아직 토큰을 입력하지 않은 첫 접속"이지 값을 찍어보는 공격이 아니다.
    headers = {"WWW-Authenticate": "Bearer"}
    if presented and _register_failure_and_check_limit():
        headers["Retry-After"] = str(_RETRY_AFTER_SECONDS)
    return JSONResponse(
        status_code=401,
        content={"detail": "인증이 필요합니다"},
        headers=headers,
    )
