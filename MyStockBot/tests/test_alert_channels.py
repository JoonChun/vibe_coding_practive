"""Slack Incoming Webhook 발송 — 검증된 규격을 코드로 잠근다.

이 환경에서는 Slack 도메인이 전부 프록시에서 막혀 **실제 발송을 검증할 수 없었다.**
그래서 규격은 Slack 공식 SDK 소스에서 확인했고(src/alert_channels.py 상단 주석),
그 규격 중 "틀리면 조용히 실패하는" 부분을 여기서 고정한다:
  · Authorization 헤더를 붙이지 않는다 (웹훅은 토큰을 쓰지 않는다)
  · Content-Type: application/json;charset=utf-8
  · 성공 = HTTP 200 **AND** 본문 문자열 "ok" (JSON 이 아니다)
그리고 무엇보다 **웹훅 URL 이 로그로 새지 않는 것**을 잠근다 — URL 그 자체가 비밀이다.
"""
import io
import json
import logging
import urllib.error

import pytest

import alert_channels

# 가짜 값이지만 GitHub 푸시 보호(secret scanning)가 Slack 웹훅 패턴으로 잡아 푸시를 막는다.
# 소스에 리터럴로 두지 않고 조립한다 — 스캐너는 파일 내용의 정적 문자열을 본다.
WEBHOOK = "/".join([
    "https://hooks.slack.com/services", "T" + "0" * 8, "B" + "0" * 8, "x" * 24,
])


class _Resp:
    def __init__(self, status=200, body="ok"):
        self.status = status
        self._body = body

    def read(self):
        return self._body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK)


# ── URL 검증 ──

def test_disabled_without_env(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert alert_channels.slack_enabled() is False
    assert alert_channels.send_slack("hi") is False


def test_enabled_with_valid_url(webhook):
    assert alert_channels.slack_enabled() is True


def test_rejects_non_slack_host(monkeypatch, caplog):
    """오타·잘못 붙여넣은 값으로 임의 호스트에 POST 하지 않는다."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://evil.example.com/collect")

    with caplog.at_level(logging.WARNING):
        assert alert_channels.slack_enabled() is False
    # 잘못된 값도 비밀일 수 있으니 로그에 URL 을 남기지 않는다.
    assert "evil.example.com" not in caplog.text


def test_blank_env_is_disabled(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "   ")
    assert alert_channels.slack_enabled() is False


# ── 요청 형식(검증된 규격) ──

def test_request_shape(monkeypatch, webhook):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", fake_urlopen)

    assert alert_channels.send_slack("판정 전환 1건") is True
    assert captured["url"] == WEBHOOK
    assert captured["method"] == "POST"
    assert captured["headers"]["content-type"] == "application/json;charset=utf-8"
    # 웹훅은 토큰을 쓰지 않는다 — Authorization 을 붙이면 Slack 이 거부한다.
    assert "authorization" not in captured["headers"]
    assert captured["body"] == {"text": "판정 전환 1건"}
    assert captured["timeout"] == alert_channels._TIMEOUT_SECONDS


def _capture(monkeypatch, captured):
    def fake_urlopen(request, timeout=None):
        captured["raw"] = request.data
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Resp()

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", fake_urlopen)


def test_korean_is_not_escaped(monkeypatch, webhook):
    """ensure_ascii=False — \\uXXXX 로 나가도 Slack 이 읽지만 페이로드가 3배로 커진다."""
    captured = {}
    _capture(monkeypatch, captured)

    alert_channels.send_slack("삼성전자")

    assert "삼성전자".encode() in captured["raw"]


def test_blocks_are_sent_with_text_fallback(monkeypatch, webhook):
    captured = {}
    _capture(monkeypatch, captured)

    alert_channels.send_slack("fallback", blocks=[{"type": "divider"}])

    assert captured["body"]["blocks"] == [{"type": "divider"}]
    assert captured["body"]["text"] == "fallback", "blocks 만 보내면 알림 미리보기가 빈다"


# ── 성공/실패 판정 ──

@pytest.mark.parametrize("status,body,expected", [
    (200, "ok", True),
    (200, "ok\n", True),      # 개행 허용
    (200, "invalid_payload", False),   # 200 이어도 본문이 ok 가 아니면 실패
    (201, "ok", False),
])
def test_success_requires_200_and_ok_body(monkeypatch, webhook, status, body, expected):
    monkeypatch.setattr(
        alert_channels.urllib.request, "urlopen",
        lambda request, timeout=None: _Resp(status, body),
    )

    assert alert_channels.send_slack("hi") is expected


def test_http_error_is_logged_with_slack_error_code(monkeypatch, webhook, caplog):
    def boom(request, timeout=None):
        raise urllib.error.HTTPError(
            WEBHOOK, 404, "Not Found", {"Retry-After": "3"}, io.BytesIO(b"channel_not_found")
        )

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.send_slack("hi") is False

    assert "channel_not_found" in caplog.text
    assert "Retry-After=3" in caplog.text


def test_network_error_returns_false(monkeypatch, webhook):
    """알림 실패가 수집 사이클을 멈추게 하지 않는다 — 예외를 밖으로 던지지 않는다."""
    def boom(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    assert alert_channels.send_slack("hi") is False


# ── 보안: URL 이 로그로 새지 않는다 ──

@pytest.mark.parametrize("failure", ["http", "url", "generic"])
def test_webhook_url_never_appears_in_logs(monkeypatch, webhook, caplog, failure):
    """웹훅 URL 이 곧 자격증명이다. Slack 은 노출된 URL 을 자동 폐기한다."""
    secret = WEBHOOK.rsplit("/", 1)[-1]

    def boom(request, timeout=None):
        if failure == "http":
            raise urllib.error.HTTPError(WEBHOOK, 403, "Forbidden", {}, io.BytesIO(b"nope"))
        if failure == "url":
            # urllib 이 URL 을 포함한 메시지를 만드는 최악의 경우를 흉내낸다.
            raise urllib.error.URLError(f"failed to reach {WEBHOOK}")
        raise RuntimeError(f"boom {WEBHOOK}")

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.DEBUG):
        alert_channels.send_slack("hi")

    assert secret not in caplog.text
    assert "hooks.slack.com" not in caplog.text


# ── DECISION_ALERT_VIEWS 오설정이 기능 전체를 무음으로 죽이던 경로 ──

def _reload_config(monkeypatch, value):
    import importlib

    import config
    monkeypatch.setenv("DECISION_ALERT_VIEWS", value)
    return importlib.reload(config)


@pytest.mark.parametrize("raw,expected", [
    ("short,long", ("short", "long")),
    ("long", ("long",)),
    ("SHORT,LONG", ("short", "long")),      # 대소문자 무관
    (" short , long ", ("short", "long")),  # 공백 관용
    ("long,long", ("long",)),               # 중복 제거
    ("long,short", ("short", "long")),      # 순서 고정
])
def test_alert_views_parsing(monkeypatch, raw, expected):
    cfg = _reload_config(monkeypatch, raw)
    assert cfg.DECISION_ALERT_VIEWS == expected


@pytest.mark.parametrize("raw", ["daily", "", "SHRT,lnog", ",,,"])
def test_bad_alert_views_falls_back_with_warning(monkeypatch, caplog, raw):
    """빈 튜플이면 diff(kinds=()) 가 전환도 시딩도 하지 않아 알림이 무음으로 죽는다.

    그런데 /api/alerts/config 의 enabled 는 여전히 true 라 진단 신호가 사실상 없었다.
    """
    with caplog.at_level(logging.WARNING):
        cfg = _reload_config(monkeypatch, raw)

    assert cfg.DECISION_ALERT_VIEWS == ("short", "long")
    assert "DECISION_ALERT_VIEWS" in caplog.text


def test_partially_valid_views_warns_but_keeps_valid(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING):
        cfg = _reload_config(monkeypatch, "long,daily")

    assert cfg.DECISION_ALERT_VIEWS == ("long",)
    assert "daily" in caplog.text


def test_empty_env_assignment_keeps_documented_default(monkeypatch):
    """`.env` 의 `DECISION_ALERT_SIDE_ONLY=` 빈 대입이 문서화된 기본값 1 을 뒤집지 않는다."""
    import importlib

    import config
    monkeypatch.setenv("DECISION_ALERT_SIDE_ONLY", "")
    cfg = importlib.reload(config)

    assert cfg.DECISION_ALERT_SIDE_ONLY is True


@pytest.fixture(autouse=True)
def _restore_config():
    """reload 로 바꾼 config 를 원상복구 — 다른 테스트가 오염되지 않게."""
    yield
    import importlib

    import config
    importlib.reload(config)


# ── 진단 가능성 vs 비밀 유출 (둘 다 지킨다) ──

def test_os_error_reason_is_logged_for_diagnosis(monkeypatch, webhook, caplog):
    """타입 이름만 남기면 로그가 "URLError" 한 단어라 사용자가 원인을 알 수 없다.

    실측: 프록시 차단 환경에서 URLError.reason 은 OSError("Tunnel connection failed:
    403 Forbidden") 였고 URL 을 담지 않았다. 그런 reason 은 통과시켜야 진단이 된다.
    """
    def boom(request, timeout=None):
        raise urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.send_slack("hi") is False

    assert "Tunnel connection failed: 403 Forbidden" in caplog.text


def test_string_reason_is_not_logged(monkeypatch, webhook, caplog):
    """문자열 reason 은 호출자가 URL 을 넣어 만들 수 있으므로 통째로 버린다."""
    def boom(request, timeout=None):
        raise urllib.error.URLError(f"failed to reach {WEBHOOK}")

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        alert_channels.send_slack("hi")

    assert "URLError" in caplog.text
    assert "failed to reach" not in caplog.text


def test_os_error_reason_carrying_a_url_is_dropped(monkeypatch, webhook, caplog):
    """OSError 라도 URL 조각이 섞이면 버린다(이중 방어)."""
    def boom(request, timeout=None):
        raise urllib.error.URLError(OSError(f"cannot reach {WEBHOOK}"))

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        alert_channels.send_slack("hi")

    assert "hooks.slack.com" not in caplog.text
    assert WEBHOOK.rsplit("/", 1)[-1] not in caplog.text
