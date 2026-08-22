"""README 의 실행 방법이 **정말로 동작하는지** 실제 서버를 띄워 확인한다.

## 왜 이 파일이 필요한가
유닛테스트 414건이 전부 통과하는데도 사용자가 README 대로 실행했을 때 에러가 났다.
단위테스트는 앱을 **띄우지** 않으므로 그 경로를 검증하지 못한다. 문서에 적은 명령이
깨지면 "테스트는 초록인데 못 쓰는 소프트웨어"가 된다 — 이 저장소가 반복해서 물린 패턴이다.

그래서 여기서는 서브프로세스로 진짜 서버를 띄우고 HTTP 로 때린다. 느리지만(≈5초)
이 경로를 대신 검증할 방법이 없다.

## 잠그는 계약
  ① `python -m uvicorn server.main:app` 이 MyStockBot/ 에서 뜬다.
  ② 포트가 이미 쓰이면 **원인을 알 수 있는 메시지**로 죽는다(조용히 실패하지 않는다).
  ③ web/dist 가 있으면 `/` 가 화면을, 없으면 API 만 — 어느 쪽이든 기동은 성공한다.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / "web" / "dist"
BOOT_TIMEOUT = 45.0


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, timeout: float = 5.0):
    """(status, body, content_type). HTTPError 도 응답으로 취급한다."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


class Server:
    """`python -m uvicorn server.main:app` 을 문서와 같은 방식으로 띄운다."""

    def __init__(self, tmp_path, port=None, extra_env=None):
        self.port = port or _free_port()
        env = {
            **os.environ,
            "MYSTOCKBOT_DB_PATH": str(tmp_path / "smoke.db"),
            "MYSTOCKBOT_API_TOKEN": "",       # 인증 비활성 — 기동 경로만 본다
            "DECISION_ALERT_ENABLED": "0",
            "KIS_MINUTE_ENABLED": "",
            **(extra_env or {}),
        }
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.main:app",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(BASE),                     # README 가 전제하는 실행 위치
            env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def wait_ready(self, timeout=BOOT_TIMEOUT) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                return False                   # 죽었다
            try:
                status, _, _ = _get(f"{self.base_url}/api/health", timeout=2)
                if status == 200:
                    return True
            except Exception:
                time.sleep(0.25)
        return False

    def stop(self) -> str:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        return self.proc.stdout.read() if self.proc.stdout else ""


@pytest.fixture
def server(tmp_path):
    s = Server(tmp_path)
    ready = s.wait_ready()
    if not ready:
        log = s.stop()
        pytest.fail(f"서버가 기동하지 못했다.\n--- 출력 ---\n{log}")
    yield s
    s.stop()


# ── ① 문서대로 뜨는가 ──

def test_documented_command_boots(server):
    status, body, _ = _get(f"{server.base_url}/api/health")
    assert status == 200
    assert b'"status":"ok"' in body.replace(b" ", b"")


def test_api_routes_respond(server):
    for path in ("/api/market/status", "/api/watchlist", "/api/alerts/config"):
        status, _, ctype = _get(f"{server.base_url}{path}")
        assert status == 200, f"{path} → {status}"
        assert "application/json" in ctype


def test_unknown_api_path_is_json_404(server):
    status, body, ctype = _get(f"{server.base_url}/api/definitely-not-here")
    assert status == 404
    assert "application/json" in ctype
    assert b"Not Found" in body


# ── ② 포트 충돌은 원인을 알 수 있게 죽는다 ──

def test_port_conflict_says_address_in_use(server, tmp_path):
    """같은 포트로 하나 더 띄우면 즉시, 그리고 **읽을 수 있는 이유로** 죽어야 한다.

    사용자가 실제로 물린 함정이다 — 기존 서버가 8000 을 쓰고 있는데 문서가 포트를
    지정하지 않는 명령을 안내했다.
    """
    second = Server(tmp_path, port=server.port)
    try:
        deadline = time.monotonic() + 20
        while second.proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.25)
        assert second.proc.poll() is not None, "포트가 겹쳤는데도 살아 있다"
        log = second.stop()
        assert "address already in use" in log.lower() or "errno 98" in log.lower(), (
            f"포트 충돌 이유가 로그에 없다:\n{log}"
        )
    finally:
        second.stop()


# ── ③ UI 서빙 ──

@pytest.mark.skipif(not (DIST / "index.html").is_file(),
                    reason="web/dist 없음 — `cd web && npm run build` 후에만 검증 가능")
def test_built_ui_is_served(server):
    status, body, ctype = _get(f"{server.base_url}/")
    assert status == 200
    assert "text/html" in ctype
    assert b"<div id=\"root\"" in body or b"<div id='root'" in body, "SPA 루트가 없다"


@pytest.mark.skipif(not (DIST / "index.html").is_file(),
                    reason="web/dist 없음")
def test_client_route_refresh_serves_the_app(server):
    """`/paper` 를 새로고침해도 화면이 떠야 한다(SPA 폴백)."""
    status, _, ctype = _get(f"{server.base_url}/paper")
    assert status == 200
    assert "text/html" in ctype


def test_boots_without_a_web_build(tmp_path, monkeypatch):
    """빌드가 없어도 기동은 성공해야 한다 — API 만 뜬다.

    dist 를 지울 수 없으니, 마운트 대상 경로가 없는 상황을 환경변수로 만들지 않고
    server.static 을 직접 검증한다(tests/test_static_ui.py 와 역할이 다르다:
    여기서는 "그래도 서버가 뜬다"는 것만 본다).
    """
    from fastapi import FastAPI

    from server.static import mount_web_ui

    app = FastAPI()
    assert mount_web_ui(app, tmp_path / "no-dist") is False
    assert app.routes, "라우트가 사라졌다"


# ── ④ 문서가 같은 실수를 반복하지 않는다 ──

def _doc_code_blocks(path: Path) -> list[str]:
    """마크다운의 ``` 코드블록 안 줄만 모은다(설명 문장은 제외)."""
    lines, inside, out = path.read_text(encoding="utf-8").splitlines(), False, []
    for line in lines:
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if inside:
            out.append(line)
    return out


@pytest.mark.parametrize("doc", ["README.md", "DEPLOY.md"])
def test_docs_never_tell_you_to_run_bare_uvicorn(doc):
    """`uvicorn ...` 로 안내하면 콘솔 스크립트가 PATH 에 없는 환경에서 막힌다.

    실제로 사용자가 이걸로 막혔다. `python -m uvicorn` 만 안내한다.
    (Dockerfile 의 CMD 는 예외 — 이미지 안에서는 PATH 가 보장된다.)
    """
    offenders = [
        line for line in _doc_code_blocks(BASE / doc)
        if "uvicorn" in line and "-m uvicorn" not in line and "docker" not in line
    ]
    assert not offenders, f"{doc} 가 맨 uvicorn 실행을 안내한다: {offenders}"


def test_readme_documents_the_run_script():
    """실행 스크립트가 있는데 문서가 모르면 아무도 안 쓴다."""
    text = (BASE / "README.md").read_text(encoding="utf-8")
    assert "scripts/run_local.sh" in text


def test_run_script_is_committed_and_executable():
    script = BASE / "scripts" / "run_local.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK), "실행 권한이 없으면 문서의 ./scripts/... 가 실패한다"
