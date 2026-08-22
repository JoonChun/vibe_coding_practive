"""KIS 자격증명이 없을 때 — 재시도해도 해결되지 않는 실패를 재시도하지 않는다.

## 왜 이 파일이 필요한가
실서버를 띄워 보니, KIS 자격증명이 없으면 `kis_ws` 가 백오프 상한(60초)에 걸린 뒤
**1분마다 영원히** 경고를 찍었다:

    WARNING [kis_ws] approval_key 발급 실패 — 60초 후 재시도:
            KIS_APP_KEY 또는 KIS_APP_SECRET 환경변수가 없습니다.

자격증명은 프로세스 시작 시 `load_dotenv` 로 한 번 읽으므로 **실행 중에 생길 수 없다.**
즉 이 재시도는 성공할 가능성이 0이면서 로그를 도배한다. "KIS 없이도 쓸 수 있다"고
안내해 둔 구성에서 앱이 고장난 것처럼 보이는 것이 문제다.

## 문구가 아니라 타입으로 구분한다
kis_auth 의 모든 실패가 같은 `RuntimeError` 였다. 메시지 문자열로 가르면 문구를 고치는
순간 조용히 오분류된다(이 저장소가 SQLite 락 분류에서 이미 겪은 함정). 그래서 전용
예외 `MissingCredentialsError` 를 만들고, 그것만 "재시도 불가"로 취급한다.
`RuntimeError` 를 상속해 기존 `except RuntimeError` 호출부의 동작은 그대로 둔다.
"""
import asyncio
import logging

import pytest

import kis_auth
from server.services import kis_ws


@pytest.fixture(autouse=True)
def _no_credentials(monkeypatch):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    # 캐시가 남아 있으면 발급 경로를 타지 않는다.
    monkeypatch.setattr(kis_auth, "_APPROVAL_KEY_CACHE", None, raising=False)
    monkeypatch.setattr(kis_auth, "_load_cache", lambda: None)


# ── 예외 타입 ──

def test_missing_credentials_error_exists_and_is_a_runtime_error():
    """RuntimeError 를 상속해야 기존 호출부(except RuntimeError)가 그대로 동작한다."""
    assert issubclass(kis_auth.MissingCredentialsError, RuntimeError)


def test_approval_key_raises_missing_credentials(monkeypatch):
    monkeypatch.setattr(kis_auth, "_load_approval_key_cache", lambda: None)

    with pytest.raises(kis_auth.MissingCredentialsError):
        kis_auth.get_approval_key()


def test_rest_token_raises_missing_credentials():
    """REST 접근토큰 경로도 같은 타입이어야 한다(경로가 둘이다)."""
    with pytest.raises(kis_auth.MissingCredentialsError):
        kis_auth.get_token()


def test_other_failures_are_not_missing_credentials(monkeypatch):
    """자격증명은 있는데 요청이 실패한 경우는 재시도 대상이다 — 구분되어야 한다."""
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    monkeypatch.setattr(kis_auth, "_load_approval_key_cache", lambda: None)

    def boom(*a, **k):
        # requests 는 소켓 오류를 RequestException 으로 감싸 던진다 — 그 계약을 따른다.
        raise kis_auth.requests.RequestException("네트워크 실패")

    monkeypatch.setattr(kis_auth.requests, "post", boom)
    monkeypatch.setattr(kis_auth.time, "sleep", lambda _s: None)   # 재시도 백오프 생략

    with pytest.raises(RuntimeError) as caught:
        kis_auth.get_approval_key()
    assert not isinstance(caught.value, kis_auth.MissingCredentialsError), (
        "네트워크 실패를 '자격증명 없음'으로 오분류했다"
    )


# ── 연결 루프 ──

def _run_loop_once(monkeypatch, raiser, timeout=3.0):
    """_connection_loop 를 돌리고 (끝났는지, 잠든 횟수) 를 돌려준다."""
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= 3:          # 무한 재시도라면 여기서 멈춰 세운다
            raise asyncio.CancelledError
        return True

    monkeypatch.setattr(kis_ws, "_interruptible_sleep", fake_sleep)
    monkeypatch.setattr(kis_auth, "get_approval_key", raiser)

    async def drive():
        kis_ws._stop_event = asyncio.Event()
        try:
            await asyncio.wait_for(kis_ws._connection_loop(), timeout)
            return True, sleeps       # 스스로 끝났다
        except (asyncio.CancelledError, asyncio.TimeoutError):
            return False, sleeps      # 계속 돌고 있었다

    return asyncio.run(drive())


def test_loop_stops_when_credentials_are_missing(monkeypatch, caplog):
    """재시도해도 성공할 수 없으므로 루프를 끝낸다 — 로그 도배를 만들지 않는다."""
    def raiser():
        raise kis_auth.MissingCredentialsError("자격증명 없음")

    with caplog.at_level(logging.INFO):
        finished, sleeps = _run_loop_once(monkeypatch, raiser)

    assert finished, "자격증명 부재인데 계속 재시도했다"
    assert sleeps == [], f"재시도 대기를 했다: {sleeps}"
    # 한 번은 알려줘야 한다 — 조용히 꺼지면 왜 실시간 시세가 없는지 알 수 없다.
    assert "자격증명" in caplog.text or "KIS_APP_KEY" in caplog.text
    assert caplog.text.count("실시간") >= 1


def test_loop_logs_only_once_for_missing_credentials(monkeypatch, caplog):
    def raiser():
        raise kis_auth.MissingCredentialsError("자격증명 없음")

    with caplog.at_level(logging.DEBUG):
        _run_loop_once(monkeypatch, raiser)

    # approval_key 관련 경고가 반복되지 않는다.
    assert caplog.text.count("approval_key") <= 1, caplog.text


def test_loop_still_retries_transient_failures(monkeypatch, caplog):
    """네트워크 실패는 재시도해야 한다 — 이 개선이 재연결을 죽이면 안 된다."""
    def raiser():
        raise RuntimeError("approval_key 발급 요청 실패: 타임아웃")

    with caplog.at_level(logging.WARNING):
        finished, sleeps = _run_loop_once(monkeypatch, raiser)

    assert not finished, "일시적 실패인데 재시도를 포기했다"
    assert len(sleeps) >= 2, f"백오프 재시도를 하지 않았다: {sleeps}"
