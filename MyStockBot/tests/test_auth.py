"""API 토큰 인증 — 틀린 토큰은 **항상** 401 이어야 한다.

## 왜 이 테스트가 생겼나
사용자가 안내 문서의 플레이스홀더를 그대로 보냈다:

    curl -H "Authorization: Bearer 여기에_토큰" ...

그리고 **401 이 아니라 500(Internal Server Error)** 이 나왔다. 원인은
`secrets.compare_digest` 가 **비ASCII `str` 을 비교하면 TypeError 를 던지는** 것이다
(실측: `compare_digest('여기에_토큰', 'x')` → TypeError). 미들웨어에서 예외가 나면
FastAPI 가 500 을 돌려준다.

두 가지가 문제다:
  · 틀린 토큰이 401 대신 500 이면 사용자는 "서버가 고장났다"고 읽는다 — 실제로 그렇게 읽혔다.
  · 토큰 자체를 비ASCII 로 설정하면(한글 토큰) **모든 인증 요청이 500** 이 된다. 즉
    인증을 켜는 순간 서버가 통째로 못 쓰게 된다.

`_API_TOKEN` 은 모듈 로드 시 1회만 읽히므로, 테스트는 환경변수를 세팅한 뒤 모듈을
재로드해서 검증한다.
"""
import asyncio
import importlib
import os

import pytest


def _load_auth(token: str | None):
    """MYSTOCKBOT_API_TOKEN 을 주고 auth 모듈을 새로 로드한다."""
    from config import API_TOKEN_ENV_KEY

    old = os.environ.get(API_TOKEN_ENV_KEY)
    if token is None:
        os.environ.pop(API_TOKEN_ENV_KEY, None)
    else:
        os.environ[API_TOKEN_ENV_KEY] = token
    try:
        from server import auth
        return importlib.reload(auth), old
    except Exception:  # pragma: no cover - 로드 실패 시 환경 복구
        if old is None:
            os.environ.pop(API_TOKEN_ENV_KEY, None)
        else:
            os.environ[API_TOKEN_ENV_KEY] = old
        raise


def _restore(old: str | None):
    from config import API_TOKEN_ENV_KEY

    if old is None:
        os.environ.pop(API_TOKEN_ENV_KEY, None)
    else:
        os.environ[API_TOKEN_ENV_KEY] = old
    from server import auth
    importlib.reload(auth)


class _Req:
    """미들웨어가 보는 최소 요청 — Request 를 만들지 않고 필요한 속성만 흉내낸다."""

    def __init__(self, header: str | None = None, method: str = "POST",
                 path: str = "/api/alerts/test"):
        self.method = method
        self.headers = {} if header is None else {"Authorization": header}
        self.url = type("U", (), {"path": path})()


async def _call(auth_mod, request):
    """auth_middleware 를 직접 호출. 통과하면 call_next 결과("PASSED")를 받는다."""
    async def call_next(_):
        return "PASSED"

    return await auth_mod.auth_middleware(request, call_next)


@pytest.fixture
def auth_with_token():
    mod, old = _load_auth("s3cret-token")
    yield mod
    _restore(old)


def test_correct_token_passes(auth_with_token):
    got = asyncio.run(_call(auth_with_token, _Req("Bearer s3cret-token")))
    assert got == "PASSED"


def test_wrong_ascii_token_is_401(auth_with_token):
    got = asyncio.run(_call(auth_with_token, _Req("Bearer wrong-token")))
    assert got.status_code == 401


def test_missing_header_is_401(auth_with_token):
    got = asyncio.run(_call(auth_with_token, _Req(None)))
    assert got.status_code == 401


def test_wrong_scheme_is_401(auth_with_token):
    got = asyncio.run(_call(auth_with_token, _Req("Basic s3cret-token")))
    assert got.status_code == 401


def test_non_ascii_token_is_401_not_500(auth_with_token):
    """★ 이 테스트가 실제 사고를 재현한다. 예외가 새어나가면 500 이 된다."""
    got = asyncio.run(_call(auth_with_token, _Req("Bearer 여기에_토큰")))
    assert got.status_code == 401


def test_emoji_and_latin1_tokens_are_401(auth_with_token):
    for bad in ["Bearer 🔑", "Bearer café", "Bearer \udcff"]:
        got = asyncio.run(_call(auth_with_token, _Req(bad)))
        assert got.status_code == 401, bad


def test_health_is_exempt(auth_with_token):
    got = asyncio.run(_call(auth_with_token, _Req(None, "GET", "/api/health")))
    assert got == "PASSED"


def test_options_is_exempt(auth_with_token):
    got = asyncio.run(_call(auth_with_token, _Req(None, "OPTIONS")))
    assert got == "PASSED"


def test_non_api_path_is_exempt(auth_with_token):
    got = asyncio.run(_call(auth_with_token, _Req(None, "GET", "/docs")))
    assert got == "PASSED"


def test_no_token_configured_disables_auth():
    mod, old = _load_auth(None)
    try:
        assert mod.is_auth_enabled() is False
        assert asyncio.run(_call(mod, _Req(None))) == "PASSED"
    finally:
        _restore(old)


def test_non_ascii_configured_token_still_works():
    """토큰을 한글로 설정해도 서버가 동작해야 한다(500 이 아니라 정상 인증).

    이걸 막지 않으면 "인증을 켜는 순간 전부 500" 이라는 최악의 실패가 남는다.
    """
    mod, old = _load_auth("한글토큰-ok")
    try:
        assert asyncio.run(_call(mod, _Req("Bearer 한글토큰-ok"))) == "PASSED"
        assert asyncio.run(_call(mod, _Req("Bearer 다른토큰"))).status_code == 401
    finally:
        _restore(old)


# ── WebSocket 스트림도 같은 비교를 쓴다 ──────────────────────────────────
def test_stream_non_ascii_token_does_not_raise():
    """stream.py 의 토큰 검사도 같은 결함을 갖고 있었다.

    여기서 예외가 나면 WS 핸드셰이크가 4401(인증 실패)이 아니라 예외로 끊긴다.
    """
    from config import API_TOKEN_ENV_KEY

    old = os.environ.get(API_TOKEN_ENV_KEY)
    os.environ[API_TOKEN_ENV_KEY] = "s3cret-token"
    try:
        from server.routers import stream
        importlib.reload(stream)
        assert stream._is_authorized("s3cret-token") is True
        assert stream._is_authorized("wrong") is False
        assert stream._is_authorized("여기에_토큰") is False   # ← 예외가 나면 실패
        assert stream._is_authorized(None) is False
    finally:
        if old is None:
            os.environ.pop(API_TOKEN_ENV_KEY, None)
        else:
            os.environ[API_TOKEN_ENV_KEY] = old
        from server.routers import stream as s
        importlib.reload(s)
