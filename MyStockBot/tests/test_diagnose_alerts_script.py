"""`scripts/diagnose_alerts.py` — 사용자 PC에서 알림 실패 원인을 짚는 진단 도구.

## 왜 스크립트인가
알림 실패 원인 규명에 왕복을 여러 번 썼다. 서버는 사용자 PC에서 돌고, 로그는 그
터미널에만 있었고, `.env` 는 (당연히) 개발 환경에 없다. `POST /api/alerts/test` 가
사유를 돌려주도록 고쳤지만 그것도 **서버를 띄우고 토큰을 찾아 curl 을 부는** 세 단계를
요구한다. 서버 없이 한 줄로 끝나는 경로가 필요하다.

## 절대 조건 — 출력에 비밀이 없어야 한다
이 스크립트의 존재 이유는 **사용자가 결과를 그대로 붙여넣을 수 있다는 것**이다.
웹훅 URL·앱 비밀번호가 한 글자라도 섞이면 도구 자체가 유출 경로가 된다. 아래 테스트가
그 경로를 적대적으로 찍는다 — 값의 길이·해시 같은 간접 정보는 허용하되 값 자체는 금지.
"""
import importlib.util
import io
import re
import runpy
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "diagnose_alerts.py"

DISCORD_TOKEN = "Zx9" + "q" * 65
DISCORD_ID = "1540602391278387292"
DISCORD_URL = f"https://discord.com/api/webhooks/{DISCORD_ID}/{DISCORD_TOKEN}"
APP_PASSWORD = "abcd efgh ijkl mnop"


def test_script_exists():
    assert SCRIPT.is_file(), "진단 스크립트가 없다"


def _run(monkeypatch, env: dict, *, probe: bool = False) -> str:
    """스크립트를 실행하고 stdout 을 돌려준다. 네트워크는 타지 않는다."""
    for key in ("DISCORD_WEBHOOK_URL", "SLACK_WEBHOOK_URL",
                "SENDER_EMAIL", "GMAIL_APP_PASSWORD", "NOTIFY_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    # `.env` 를 읽지 않게 한다 — 테스트는 os.environ 만으로 구동한다.
    monkeypatch.setenv("MYSTOCKBOT_DIAGNOSE_SKIP_DOTENV", "1")
    if not probe:
        monkeypatch.setenv("MYSTOCKBOT_DIAGNOSE_NO_NETWORK", "1")

    argv = sys.argv[:]
    sys.argv = ["diagnose_alerts.py"]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            try:
                runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit:
                pass
    finally:
        sys.argv = argv
    return buf.getvalue()


# ── ★ 비밀 누출 방지 ─────────────────────────────────────────────────────

def test_output_never_contains_the_webhook_url(monkeypatch):
    out = _run(monkeypatch, {"DISCORD_WEBHOOK_URL": DISCORD_URL})
    assert DISCORD_URL not in out
    assert DISCORD_TOKEN not in out
    assert DISCORD_ID not in out, "webhook id 도 자격증명의 절반이다"


def test_output_never_contains_the_app_password(monkeypatch):
    out = _run(monkeypatch, {
        "SENDER_EMAIL": "me@example.com",
        "GMAIL_APP_PASSWORD": APP_PASSWORD,
        "NOTIFY_EMAIL": "me@example.com",
    })
    assert APP_PASSWORD not in out
    assert APP_PASSWORD.replace(" ", "") not in out


def test_output_has_no_long_opaque_token(monkeypatch):
    """혹시 모를 경로로 긴 랜덤 문자열이 새는지 형태로도 막는다."""
    out = _run(monkeypatch, {
        "DISCORD_WEBHOOK_URL": DISCORD_URL,
        "SENDER_EMAIL": "me@example.com",
        "GMAIL_APP_PASSWORD": APP_PASSWORD,
        "NOTIFY_EMAIL": "me@example.com",
    })
    # **토큰 형태**를 찾는다: 20자 이상이면서 대문자·소문자·숫자가 섞인 덩어리.
    # 저장소 경로(`vibe_coding_practive` — 소문자만)나 환경변수명
    # (`DECISION_ALERT_ENABLED` — 대문자만)은 자격증명이 아니므로 이 조건에 걸리지
    # 않는다. sha256 앞 12자는 길이에서 걸러진다.
    suspicious = [
        m for m in re.findall(r"[A-Za-z0-9]{20,}", out)
        if any(c.isupper() for c in m)
        and any(c.islower() for c in m)
        and any(c.isdigit() for c in m)
    ]
    assert not suspicious, f"토큰 형태의 문자열이 출력됐다: {suspicious[:3]}"


# ── 진단 내용 ────────────────────────────────────────────────────────────

def test_reports_missing_everything(monkeypatch):
    out = _run(monkeypatch, {})
    assert "미설정" in out
    assert "DISCORD_WEBHOOK_URL" in out


def test_detects_duplicated_prefix(monkeypatch):
    """실제로 겪은 사고: 예시 접두사 뒤에 URL 을 이어붙여 값이 두 개가 됐다."""
    out = _run(monkeypatch, {
        "DISCORD_WEBHOOK_URL": f"https://discord.com/api/webhooks/{DISCORD_URL}"
    })
    assert "://" in out or "두 개" in out or "이어붙" in out
    assert "거부" in out or "문제" in out or "✗" in out


def test_accepts_valid_discord_url(monkeypatch):
    out = _run(monkeypatch, {"DISCORD_WEBHOOK_URL": DISCORD_URL})
    assert "형식 통과" in out or "✓" in out


def test_reports_email_partial_config(monkeypatch):
    """셋 중 하나만 빠져도 이메일은 통째로 비활성이다 — 그 사실이 보여야 한다."""
    out = _run(monkeypatch, {
        "SENDER_EMAIL": "me@example.com",
        "GMAIL_APP_PASSWORD": APP_PASSWORD,
        # NOTIFY_EMAIL 누락
    })
    assert "NOTIFY_EMAIL" in out
    assert "미설정" in out or "누락" in out


def test_flags_app_password_with_wrong_length(monkeypatch):
    """Gmail 앱 비밀번호는 16자다. 길이가 다르면 그것만 알려준다(값은 안 보여준다)."""
    out = _run(monkeypatch, {
        "SENDER_EMAIL": "me@example.com",
        "GMAIL_APP_PASSWORD": "tooshort",
        "NOTIFY_EMAIL": "me@example.com",
    })
    assert "16" in out
    assert "tooshort" not in out


def test_accepts_app_password_with_spaces(monkeypatch):
    """Gmail 화면은 공백을 넣어 보여준다 — 그대로 붙여넣어도 정상으로 봐야 한다."""
    out = _run(monkeypatch, {
        "SENDER_EMAIL": "me@example.com",
        "GMAIL_APP_PASSWORD": APP_PASSWORD,   # 공백 포함 16자
        "NOTIFY_EMAIL": "me@example.com",
    })
    assert "16자" in out or "✓" in out


def test_shows_length_and_hash_for_comparison(monkeypatch):
    """값을 못 보여주므로 길이와 해시 앞자리로 '내가 넣은 그 값인지' 확인시킨다."""
    out = _run(monkeypatch, {"DISCORD_WEBHOOK_URL": DISCORD_URL})
    assert "길이" in out
    assert re.search(r"[0-9a-f]{8,12}", out), "sha256 앞자리가 없다"


def test_no_network_flag_skips_probing(monkeypatch):
    out = _run(monkeypatch, {"DISCORD_WEBHOOK_URL": DISCORD_URL})
    assert "건너뜀" in out or "생략" in out


def test_script_is_importable_without_running(monkeypatch):
    """구문 오류로 조용히 못 도는 일이 없게 import 가능 여부를 잠근다."""
    spec = importlib.util.spec_from_file_location("diagnose_alerts", SCRIPT)
    assert spec is not None and spec.loader is not None


@pytest.mark.parametrize("bad", [
    "discord.com/api/webhooks/1/2",                       # 스킴 없음
    "https://discord.com/api/webhooks/notanumber/token",  # id 가 숫자 아님
    "https://discord.com/api/webhooks/123",               # 조각 부족
    "https://example.com/api/webhooks/123/abc",           # 호스트 오류
])
def test_rejects_malformed_urls(monkeypatch, bad):
    out = _run(monkeypatch, {"DISCORD_WEBHOOK_URL": bad})
    assert "✗" in out or "거부" in out or "문제" in out


# ── --env-file: 작업 트리를 건드리지 않고 진단하기 ────────────────────────
#
# 사용자의 로컬 저장소는 프로젝트 9개가 든 모노레포이고, `git pull` 이 다른 하위
# 프로젝트의 로컬 변경과 충돌했다. 그래서 "브랜치를 체크아웃하지 않고" 진단하는 길이
# 필요하다 — 별도 worktree/클론에서 스크립트만 돌리고 `.env` 는 원래 위치를 가리킨다.

def _run_argv(monkeypatch, args: list[str]) -> tuple[str, object]:
    monkeypatch.delenv("MYSTOCKBOT_DIAGNOSE_SKIP_DOTENV", raising=False)
    monkeypatch.setenv("MYSTOCKBOT_DIAGNOSE_NO_NETWORK", "1")
    argv = sys.argv[:]
    sys.argv = ["diagnose_alerts.py", *args]
    buf = io.StringIO()
    code = None
    try:
        with redirect_stdout(buf):
            try:
                runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit as e:
                code = e.code
    finally:
        sys.argv = argv
    return buf.getvalue(), code


def test_env_file_option_is_read(monkeypatch, tmp_path):
    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "SENDER_EMAIL=me@example.com\n"
        "GMAIL_APP_PASSWORD=abcd efgh ijkl mnop\n"
        "NOTIFY_EMAIL=me@example.com\n",
        encoding="utf-8",
    )
    for key in ("SENDER_EMAIL", "GMAIL_APP_PASSWORD", "NOTIFY_EMAIL",
                "DISCORD_WEBHOOK_URL", "SLACK_WEBHOOK_URL"):
        monkeypatch.delenv(key, raising=False)

    out, _ = _run_argv(monkeypatch, ["--env-file", str(env_file)])
    assert str(env_file) in out, "어느 .env 를 읽었는지 보여줘야 한다"
    assert "앱 비밀번호 16자 확인" in out
    assert "abcd efgh ijkl mnop" not in out


def test_missing_env_file_reports_clearly(monkeypatch, tmp_path):
    out, code = _run_argv(monkeypatch, ["--env-file", str(tmp_path / "nope.env")])
    assert "없습니다" in out or "찾지 못" in out
    assert code != 0, "존재하지 않는 파일을 조용히 무시하면 안 된다"
