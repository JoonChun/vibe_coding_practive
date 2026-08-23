"""발송 실패 사유를 **응답으로** 돌려준다 — 로그를 찾아 헤매게 하지 않기 위해.

## 왜 이걸 만들었나
사용자가 `POST /api/alerts/test` 로 `{"discord": false, "email": false}` 를 받았고,
안내는 "서버 로그의 [discord]·[notifier] 경고를 확인하세요"였다. 그런데 사용자는
로그에 닿지 못했다 — 서버가 다른 터미널에서 포그라운드로 돌고 있었고, 새로 띄우려니
`address already in use` 였다. 원인 규명에 왕복 세 번을 썼고 아직 원인을 모른다.

테스트 발송 엔드포인트는 **그 자체가 진단 도구**다. 실패 사유를 로그에만 남기고
응답에는 bool 만 주는 것은 이 엔드포인트의 목적에 반한다.

## 절대 조건 — 사유에 비밀이 섞이면 안 된다
웹훅 URL 자체가 자격증명이고 Gmail 앱 비밀번호도 그렇다. 사유 문구는 API 응답으로
나가고 화면에 표시되므로, **상류가 응답 본문에 비밀을 되돌려주더라도** 그것이 사유에
실려 나가면 안 된다. 아래 테스트가 그 경로를 적대적으로 찍는다.
"""
import urllib.error

import pytest

import alert_channels
import notifier

DISCORD_ID = "1" * 19
DISCORD_TOKEN = "t" * 68
DISCORD_URL = f"https://discord.com/api/webhooks/{DISCORD_ID}/{DISCORD_TOKEN}"


class _Resp:
    def __init__(self, status=204, body=""):
        self.status = status
        self._body = body

    def read(self):
        return self._body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, body=""):
    import io
    return urllib.error.HTTPError(
        DISCORD_URL, code, "err", {}, io.BytesIO(body.encode("utf-8"))
    )


@pytest.fixture
def discord(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_URL)


# ── Discord ─────────────────────────────────────────────────────────────

def test_success_leaves_no_reason(discord, monkeypatch):
    monkeypatch.setattr(alert_channels.urllib.request, "urlopen",
                        lambda r, timeout=None: _Resp(200, "{}"))
    out: dict = {}
    assert alert_channels.send_discord("hi", out=out) is True
    assert out.get("reason") in (None, "")


def test_http_404_reason_names_the_status_and_cause(discord, monkeypatch):
    """404 = 웹훅이 존재하지 않는다(삭제·재발급 후 .env 미갱신이 대표 경로)."""
    def boom(r, timeout=None):
        raise _http_error(404, '{"message": "Unknown Webhook", "code": 10015}')

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)
    out: dict = {}
    assert alert_channels.send_discord("hi", out=out) is False
    reason = out["reason"]
    assert "404" in reason
    assert "10015" in reason or "존재하지 않" in reason


def test_http_401_reason_is_reported(discord, monkeypatch):
    def boom(r, timeout=None):
        raise _http_error(401, '{"message": "401: Unauthorized"}')

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)
    out: dict = {}
    assert alert_channels.send_discord("hi", out=out) is False
    assert "401" in out["reason"]


def test_network_error_reason_is_reported(discord, monkeypatch):
    def boom(r, timeout=None):
        raise urllib.error.URLError(OSError("[Errno -2] Name or service not known"))

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)
    out: dict = {}
    assert alert_channels.send_discord("hi", out=out) is False
    assert "Name or service not known" in out["reason"]


def test_unexpected_status_reason_is_reported(discord, monkeypatch):
    """2xx 지만 Discord 가 저장하지 않은 응답(?wait=true 규격 위반)도 사유가 남는다."""
    monkeypatch.setattr(alert_channels.urllib.request, "urlopen",
                        lambda r, timeout=None: _Resp(500, "oops"))
    out: dict = {}
    assert alert_channels.send_discord("hi", out=out) is False
    assert "500" in out["reason"]


# ── ★ 비밀 누출 방지 ─────────────────────────────────────────────────────

@pytest.mark.parametrize("body", [
    DISCORD_URL,                                  # 상류가 URL 전체를 되돌려줌
    f'{{"message": "bad token {DISCORD_TOKEN}"}}',  # 토큰만
    f'{{"message": "webhook {DISCORD_ID} gone"}}',  # id 만
    "Tunnel connection failed for discord.com",     # 호스트
])
def test_reason_never_leaks_secrets(discord, monkeypatch, body):
    """상류 응답 본문에 URL·토큰·id·호스트가 섞여 와도 사유에 실리지 않는다.

    사유는 API 응답으로 나가고 화면에 표시된다 — 여기가 유출 경로가 되면 로그를
    막아둔 모든 방어가 무의미해진다.
    """
    def boom(r, timeout=None):
        raise _http_error(404, body)

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)
    out: dict = {}
    alert_channels.send_discord("hi", out=out)
    reason = out.get("reason", "")
    assert DISCORD_TOKEN not in reason
    assert DISCORD_ID not in reason
    assert "discord.com" not in reason
    assert "404" in reason, "비밀을 지우면서 상태코드까지 잃으면 진단 가치가 없다"


def test_network_error_reason_scrubs_secrets(discord, monkeypatch):
    def boom(r, timeout=None):
        raise urllib.error.URLError(OSError(f"cannot reach {DISCORD_URL}"))

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)
    out: dict = {}
    alert_channels.send_discord("hi", out=out)
    reason = out.get("reason", "")
    assert DISCORD_TOKEN not in reason
    assert "discord.com" not in reason


# ── 이메일 ───────────────────────────────────────────────────────────────

PASSWORD = "abcd efgh ijkl mnop"


@pytest.fixture
def email_env(monkeypatch):
    monkeypatch.setenv("SENDER_EMAIL", "me@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", PASSWORD)
    monkeypatch.setenv("NOTIFY_EMAIL", "me@example.com")


def _smtp_raising(exc):
    class _S:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            raise exc

        def __exit__(self, *a):
            return False

    return _S


def test_email_auth_failure_reason_names_the_cause(email_env, monkeypatch):
    import smtplib

    exc = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    monkeypatch.setattr(notifier.smtplib, "SMTP_SSL", _smtp_raising(exc))
    out: dict = {}
    assert notifier.send_html("s", "<p>b</p>", out=out) is False
    reason = out["reason"]
    assert "SMTPAuthenticationError" in reason or "535" in reason


def test_email_reason_never_leaks_app_password(email_env, monkeypatch):
    """예외 문구에 앱 비밀번호가 섞여 와도 응답에 실리지 않는다."""
    import smtplib

    exc = smtplib.SMTPException(f"login failed for me@example.com with {PASSWORD}")
    monkeypatch.setattr(notifier.smtplib, "SMTP_SSL", _smtp_raising(exc))
    out: dict = {}
    notifier.send_html("s", "<p>b</p>", out=out)
    reason = out.get("reason", "")
    assert PASSWORD not in reason
    assert PASSWORD.replace(" ", "") not in reason
    assert reason, "비밀을 지우더라도 사유 자체는 남아야 한다"


def test_email_missing_config_reason(monkeypatch):
    monkeypatch.delenv("SENDER_EMAIL", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("NOTIFY_EMAIL", raising=False)
    out: dict = {}
    assert notifier.send_html("s", "<p>b</p>", out=out) is False
    assert "환경변수" in out["reason"] or "누락" in out["reason"]


def test_email_success_leaves_no_reason(email_env, monkeypatch):
    class _S:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, *a):
            pass

        def sendmail(self, *a):
            pass

    monkeypatch.setattr(notifier.smtplib, "SMTP_SSL", _S)
    out: dict = {}
    assert notifier.send_html("s", "<p>b</p>", out=out) is True
    assert out.get("reason") in (None, "")


# ── 기존 호출부는 그대로 동작해야 한다(out 은 선택) ─────────────────────

def test_out_is_optional(discord, monkeypatch):
    monkeypatch.setattr(alert_channels.urllib.request, "urlopen",
                        lambda r, timeout=None: _Resp(200, "{}"))
    assert alert_channels.send_discord("hi") is True


# ── SMTP 인증 거부(535)에 한 줄 요약을 붙인다 ─────────────────────────────
#
# 실측(2026-08-23 사용자 네트워크): Gmail 이
#   535, b'5.7.8 Username and Password not accepted. For more information, go to
#         5.7.8  https://support.google.com/mail/?p=BadCredentials ...'
# 를 돌려줬다. 원문은 영어 두 줄이라 한국어 사용자가 바로 읽기 어렵다. 그래서 **Google
# 이 준 문장을 다시 말하는 수준의** 요약만 앞에 붙인다.
#
# 원인 목록(2단계 인증 필요 여부 등)을 문구에 넣지 않는 이유: 이 저장소는 외부 스펙을
# 1차 출처로만 적고, Google 지원 문서는 개발 환경에서 403 으로 차단돼 확인할 수 없었다.
# 확인 못 한 정책을 단정하면 사용자를 엉뚱한 곳으로 보낸다. Google 이 응답에 넣어준
# 링크를 그대로 남겨 사용자가 1차 출처로 가게 한다.

def test_smtp_535_gets_a_korean_summary(email_env, monkeypatch):
    import smtplib

    exc = smtplib.SMTPAuthenticationError(
        535,
        b"5.7.8 Username and Password not accepted. For more information, go to\n"
        b"5.7.8  https://support.google.com/mail/?p=BadCredentials x - gsmtp",
    )
    monkeypatch.setattr(notifier.smtplib, "SMTP_SSL", _smtp_raising(exc))
    out: dict = {}
    assert notifier.send_html("s", "<p>b</p>", out=out) is False
    reason = out["reason"]
    assert "거부" in reason, "영어 원문만 주면 한국어 사용자가 바로 못 읽는다"
    assert "535" in reason
    # Google 이 준 링크는 살려둔다 — 그게 1차 출처다.
    assert "support.google.com" in reason


def test_other_smtp_errors_are_not_relabeled(email_env, monkeypatch):
    """535 가 아닌 오류에 인증 문구를 붙이면 오진을 유발한다."""
    import smtplib

    exc = smtplib.SMTPRecipientsRefused({"x@y.z": (550, b"No such user")})
    monkeypatch.setattr(notifier.smtplib, "SMTP_SSL", _smtp_raising(exc))
    out: dict = {}
    notifier.send_html("s", "<p>b</p>", out=out)
    assert "자격증명" not in out["reason"]
    assert "SMTPRecipientsRefused" in out["reason"]
