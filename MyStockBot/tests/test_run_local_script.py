"""scripts/run_local.sh — 실행 전 점검이 원인을 말해주는지 검증한다.

## 왜 이 파일이 필요한가
README 에 두 줄짜리 실행 명령을 적었더니 사용자 환경에서 에러가 났다. 원인은 두 가지
환경 가정이었다:
  · `uvicorn` 이 PATH 에 있다고 가정 → 없으면 `command not found`
  · 8000 포트가 비어 있다고 가정 → 이미 서버가 돌고 있으면 `Address already in use`
둘 다 **문서가 알려줄 수 있었던** 문제다. 그래서 실행을 스크립트로 감싸고, 실패할 때
"무엇이 문제이고 어떻게 고치는지"를 출력하게 만든 뒤, 그 출력을 여기서 잠근다.

메시지 문구를 테스트가 붙잡는 건 의도적이다 — 이 스크립트의 **산출물은 그 메시지**다.
"""
import os
import socket
import subprocess
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
SCRIPT = BASE / "scripts" / "run_local.sh"

# PATH 를 비우는 테스트가 있으므로 bash 를 절대경로로 잡는다.
BASH = next((p for p in ("/usr/bin/bash", "/bin/bash", "/usr/bin/sh", "/bin/sh")
             if Path(p).exists()), "bash")


def run(args=(), cwd=None, env_extra=None, timeout=60):
    env = {**os.environ, "MYSTOCKBOT_RUN_LOCAL_DRY": "1", **(env_extra or {})}
    return subprocess.run(
        [BASH, str(SCRIPT), *args],
        cwd=str(cwd or BASE), env=env,
        capture_output=True, text=True, timeout=timeout,
    )


@pytest.fixture
def busy_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    yield s.getsockname()[1]
    s.close()


def test_script_exists_and_is_executable():
    assert SCRIPT.is_file(), "scripts/run_local.sh 가 없다"
    assert os.access(SCRIPT, os.X_OK), "실행 권한이 없다(chmod +x)"


# ── 정상 경로(dry-run) ──

def test_dry_run_prints_the_command_it_would_use(busy_port):
    """DRY 모드는 실제로 띄우지 않고 실행할 명령만 보여준다 — 테스트가 붙잡을 지점."""
    result = run(env_extra={"PORT": str(busy_port + 1)})

    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    # PATH 의 `uvicorn` 에 의존하지 않는다 — 이게 사용자가 물린 함정 중 하나였다.
    assert "-m uvicorn" in out, f"python -m uvicorn 을 쓰지 않는다:\n{out}"
    assert "server.main:app" in out
    assert str(busy_port + 1) in out, "선택한 포트가 안 보인다"


def test_prints_the_url_to_open():
    result = run(env_extra={"PORT": "8123"})
    assert "http://localhost:8123" in result.stdout


# ── 포트 점유 ──

def test_busy_port_is_detected_before_starting(busy_port):
    """포트가 이미 쓰이면 uvicorn 의 트레이스백 대신 조치를 알려준다."""
    result = run(env_extra={"PORT": str(busy_port)})

    assert result.returncode != 0, "점유된 포트인데 성공으로 끝났다"
    combined = result.stdout + result.stderr
    assert str(busy_port) in combined
    assert "이미 사용 중" in combined, f"원인을 말해주지 않는다:\n{combined}"
    # 조치를 함께 알려준다.
    assert "PORT=" in combined, "다른 포트로 띄우는 방법을 안내하지 않는다"


# ── 실행 위치 ──

def test_wrong_directory_is_rejected_with_guidance(tmp_path):
    """server.main 의 sys.path 설정이 MyStockBot/ 실행을 전제한다."""
    result = run(cwd=tmp_path)

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "MyStockBot" in combined, f"어디서 실행해야 하는지 안 알려준다:\n{combined}"


# ── 웹 빌드 안내 ──

def test_missing_build_is_reported_but_not_fatal(tmp_path, monkeypatch):
    """빌드가 없어도 API 는 떠야 한다 — 경고만 하고 계속 간다."""
    # dist 를 실제로 지우지 않기 위해, 스크립트가 보는 경로를 바꿔 끼운다.
    result = run(env_extra={"PORT": "8124",
                            "MYSTOCKBOT_WEB_DIST": str(tmp_path / "nope")})

    assert result.returncode == 0, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "npm run build" in combined, "빌드 방법을 안내하지 않는다"


def test_existing_build_is_reported(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")

    result = run(env_extra={"PORT": "8125", "MYSTOCKBOT_WEB_DIST": str(dist)})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "npm run build" not in result.stdout, "빌드가 있는데 빌드하라고 한다"


# ── 파이썬 인터프리터 ──

def test_uses_the_python_that_has_uvicorn(tmp_path):
    """`uvicorn` 실행파일이 PATH 에 없어도 동작해야 한다.

    빈 PATH 를 주고도 스크립트가 파이썬을 찾아내는지 본다(python3 절대경로 사용).
    """
    result = run(env_extra={"PORT": "8126", "PATH": "/nonexistent"})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "-m uvicorn" in result.stdout
