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


# ══════════════════════════════════════════════════════════════════════
# Discord Webhook — 규격은 discord/discord-api-docs 원문으로 확인했다
# (developers/resources/webhook.mdx · .../message.mdx). 상세 근거는
# src/alert_channels.py 모듈 주석 참고.
# ══════════════════════════════════════════════════════════════════════

# 가짜 값. Slack 쪽과 같은 이유로 리터럴을 피해 조립한다(푸시 보호 + 실수 방지).
DISCORD_WEBHOOK = "/".join([
    "https://discord.com/api/webhooks", "1" * 19, "d" * 68,
])


@pytest.fixture
def discord(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK)


def _capture_discord(monkeypatch, captured):
    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Resp(204, "")

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", fake_urlopen)


# ── URL 검증 ──

def test_discord_disabled_without_env(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    assert alert_channels.discord_enabled() is False
    assert alert_channels.send_discord("hi") is False


def test_discord_enabled_with_valid_url(discord):
    assert alert_channels.discord_enabled() is True


def test_discord_accepts_legacy_discordapp_host(monkeypatch):
    """discordapp.com 은 구 도메인이지만 예전에 만든 웹훅 URL 이 여전히 동작한다."""
    monkeypatch.setenv(
        "DISCORD_WEBHOOK_URL",
        DISCORD_WEBHOOK.replace("discord.com", "discordapp.com"),
    )
    assert alert_channels.discord_enabled() is True


@pytest.mark.parametrize("bad", [
    "https://evil.example.com/api/webhooks/1/2",
    "https://discord.com/oauth2/authorize",          # 호스트는 맞지만 웹훅 경로가 아니다
    "http://discord.com/api/webhooks/1/2",           # 평문 HTTP
])
def test_discord_rejects_wrong_url(monkeypatch, caplog, bad):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", bad)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.discord_enabled() is False
    assert "evil.example.com" not in caplog.text


# ── 요청 형식(검증된 규격) ──

def test_discord_request_shape(discord, monkeypatch):
    captured = {}
    _capture_discord(monkeypatch, captured)

    assert alert_channels.send_discord("판정 전환 1건") is True

    assert captured["method"] == "POST"
    # 공식 문서: "this call does not require authentication" — 토큰이 URL 경로에 있다.
    assert "authorization" not in captured["headers"]
    assert captured["headers"]["content-type"] == "application/json;charset=utf-8"
    # 본문 필드는 content 다 (Slack 의 text 가 아니다).
    assert captured["body"]["content"] == "판정 전환 1건"
    assert "text" not in captured["body"]


def test_discord_always_sends_wait_true(discord, monkeypatch):
    """wait=false 면 "a message that is not saved does not return an error" —
    조용히 버려진 메시지를 성공으로 읽으면 그 전환이 영구 유실된다."""
    captured = {}
    _capture_discord(monkeypatch, captured)

    alert_channels.send_discord("hi")

    assert "wait=true" in captured["url"]


def test_discord_preserves_existing_query_string(monkeypatch):
    """사용자가 thread_id 등을 붙여 둔 URL 도 깨지지 않아야 한다."""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK + "?thread_id=123")
    captured = {}
    _capture_discord(monkeypatch, captured)

    alert_channels.send_discord("hi")

    assert "thread_id=123" in captured["url"]
    assert "wait=true" in captured["url"]


def test_discord_blocks_all_mentions_structurally(discord, monkeypatch):
    """★ 이게 Discord 경로의 핵심 보안 장치다.

    웹훅 기본값은 {"parse": ["users"]} 라서 종목명에 섞인 유저 멘션이 실제로 핑을 보낸다.
    {"parse": []} 는 텍스트 이스케이프와 달리 문자 조합으로 우회할 수 없다.
    공식 문서도 user-generated string 에 allowed_mentions 사용을 권한다.
    """
    captured = {}
    _capture_discord(monkeypatch, captured)

    alert_channels.send_discord("@everyone <@1234> @here 다 눌러도 안 된다")

    assert captured["body"]["allowed_mentions"] == {"parse": []}


# ── 성공/실패 판정 ──

@pytest.mark.parametrize("status,expected", [
    (204, True),   # wait 가 무시된 경우 (관용 허용)
    (200, True),   # wait=true 의 정상 응답
    (400, False),
    (404, False),
])
def test_discord_success_codes(discord, monkeypatch, status, expected):
    monkeypatch.setattr(
        alert_channels.urllib.request, "urlopen",
        lambda request, timeout=None: _Resp(status, "" if status == 204 else "{}"),
    )

    assert alert_channels.send_discord("hi") is expected


def test_discord_http_error_logs_rate_limit_hint(discord, monkeypatch, caplog):
    """429 는 Retry-After 헤더 + JSON retry_after 로 온다(공식 rate-limits 문서)."""
    def boom(request, timeout=None):
        raise urllib.error.HTTPError(
            DISCORD_WEBHOOK, 429, "Too Many Requests",
            {"Retry-After": "64.57"}, io.BytesIO(b'{"retry_after": 64.57, "global": false}'),
        )

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.send_discord("hi") is False

    assert "429" in caplog.text
    assert "Retry-After=64.57" in caplog.text


def test_discord_network_error_returns_false(discord, monkeypatch):
    def boom(request, timeout=None):
        raise urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    assert alert_channels.send_discord("hi") is False


# ── 보안: Discord 웹훅 URL 도 로그로 새지 않는다 ──

@pytest.mark.parametrize("failure", ["http", "url", "generic"])
def test_discord_webhook_url_never_appears_in_logs(discord, monkeypatch, caplog, failure):
    """웹훅 URL 의 마지막 조각이 토큰이다 — 노출되면 그 채널에 누구나 보낼 수 있다."""
    token = DISCORD_WEBHOOK.rsplit("/", 1)[-1]

    def boom(request, timeout=None):
        if failure == "http":
            raise urllib.error.HTTPError(
                DISCORD_WEBHOOK, 403, "Forbidden", {}, io.BytesIO(b"nope")
            )
        if failure == "url":
            raise urllib.error.URLError(OSError(f"cannot reach {DISCORD_WEBHOOK}"))
        raise RuntimeError(f"boom {DISCORD_WEBHOOK}")

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.DEBUG):
        alert_channels.send_discord("hi")

    assert token not in caplog.text
    assert "discord.com" not in caplog.text


# ── 마크다운 이스케이프 (표시 위생 — 보안은 allowed_mentions 가 담당) ──

@pytest.mark.parametrize("raw,expected", [
    ("**굵게**", "\\*\\*굵게\\*\\*"),
    ("||스포||", "\\|\\|스포\\|\\|"),
    ("`코드`", "\\`코드\\`"),
    ("a_b_c", "a\\_b\\_c"),
    ("~취소~", "\\~취소\\~"),
])
def test_escape_markdown(raw, expected):
    assert alert_channels.escape_markdown(raw) == expected


def test_escape_markdown_backslash_first():
    """`\\` 를 먼저 처리해야 한다 — 나중이면 앞서 넣은 백슬래시를 다시 이스케이프한다."""
    assert alert_channels.escape_markdown("a\\*b") == "a\\\\\\*b"
    assert alert_channels.escape_markdown(None) == ""


# ── 방언: 굵게 문법이 채널마다 다르다 ──

def test_dialects_use_different_bold_syntax():
    """서로 바꿔 보내면 별표가 글자로 보인다 — 조용히 못생겨지는 종류의 버그."""
    assert alert_channels.SLACK_DIALECT.bold("x") == "*x*"
    assert alert_channels.DISCORD_DIALECT.bold("x") == "**x**"


def test_discord_dialect_declares_the_verified_char_cap():
    """공식 문서 webhook.mdx: content "up to 2000 characters"."""
    assert alert_channels.DISCORD_DIALECT.max_chars == 2000
    # Slack 상한은 1차 출처로 확인하지 못했다 — 추측한 숫자를 넣지 않는다.
    assert alert_channels.SLACK_DIALECT.max_chars is None


# ── 채널 레지스트리 ──

def test_enabled_channels_reflects_env(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    assert alert_channels.enabled_channels() == ()

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK)
    assert [c.name for c in alert_channels.enabled_channels()] == ["discord"]

    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK)
    assert [c.name for c in alert_channels.enabled_channels()] == ["slack", "discord"]


def test_channel_registry_is_rebuilt_per_call(monkeypatch):
    """모듈 상수로 두면 import 시점 함수 객체를 붙잡아 교체가 조용히 무효화된다.

    이 저장소가 반복해서 물린 패턴이라 회귀로 잠근다.
    """
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: True)
    monkeypatch.setattr(alert_channels, "discord_enabled", lambda: False)

    assert [c.name for c in alert_channels.enabled_channels()] == ["slack"]


def test_failure_log_label_equals_channel_name(monkeypatch, caplog):
    """웹훅 채널의 실패 로그 태그 == 채널명.

    라우터의 실패 안내(`[discord] 경고 확인`)는 채널명을 그대로 태그로 쓴다
    (server/services/alerts.py::log_tag 의 기본 분기). 그 동일성이 깨지면 안내가
    로그에 없는 태그를 가리키게 되므로 여기서 잠근다.
    """
    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK)

    def boom(request, timeout=None):
        raise urllib.error.URLError(OSError("Name or service not known"))

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    for channel in alert_channels.all_channels():
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="alert_channels"):
            assert channel.send("본문") is False
        assert f"[{channel.name}]" in caplog.text, (
            f"{channel.name} 채널의 실패 로그가 [{channel.name}] 태그로 찍히지 않는다"
        )


# ── 상태별 조치 안내 ──

def test_discord_404_log_says_what_to_do(discord, monkeypatch, caplog):
    """404 는 "웹훅이 없다"는 뜻이라 조치가 정해져 있다 — 로그가 그걸 알려줘야 한다.

    1차 출처: discord/discord-api-docs opcodes-and-status-codes.mdx
      404 = "The resource at the location specified doesn't exist." / code 10015 =
      "Unknown webhook". 원인만 찍고 조치를 안 알려주면 사용자가 다음 수를 못 찾는다.
    """
    def boom(request, timeout=None):
        raise urllib.error.HTTPError(
            DISCORD_WEBHOOK, 404, "Not Found", {},
            io.BytesIO(b'{"message": "Unknown Webhook", "code": 10015}'),
        )

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.send_discord("hi") is False

    assert "404" in caplog.text
    assert "10015" in caplog.text, "응답 본문(원인)이 사라졌다"
    assert "웹훅" in caplog.text and "DISCORD_WEBHOOK_URL" in caplog.text, "조치 안내가 없다"


def test_discord_hint_does_not_replace_retry_after(discord, monkeypatch, caplog):
    """안내 문구를 붙여도 기존 Retry-After 정보를 밀어내지 않아야 한다."""
    def boom(request, timeout=None):
        raise urllib.error.HTTPError(
            DISCORD_WEBHOOK, 429, "Too Many Requests",
            {"Retry-After": "3.5"}, io.BytesIO(b'{"retry_after": 3.5}'),
        )

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.send_discord("hi") is False

    assert "Retry-After=3.5" in caplog.text


def test_slack_has_no_invented_hints(webhook, monkeypatch, caplog):
    """Slack 웹훅 오류 본문 목록은 1차 출처로 확인하지 못했다 — 문구를 지어내지 않는다.

    없는 규격을 그럴듯하게 써 두면 잘못된 방향으로 디버깅을 보낸다. 이 저장소의
    추측 금지 규칙을 코드로 잠근다.
    """
    def boom(request, timeout=None):
        raise urllib.error.HTTPError(
            WEBHOOK, 404, "Not Found", {}, io.BytesIO(b"no_service"),
        )

    monkeypatch.setattr(alert_channels.urllib.request, "urlopen", boom)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.send_slack("hi") is False

    assert "404" in caplog.text and "no_service" in caplog.text
    assert "—" not in caplog.text, "확인되지 않은 Slack 안내 문구가 붙었다"


# ── 구조 검증: startswith 만으로는 못 잡는 오염 ──

# 실사용에서 이 형태가 검증을 통과해 버렸다. README 예시 줄(접두사) 뒤에 복사한 URL 을
# 이어 붙인 값이다. 앞 33자가 맞으니 startswith 검사를 통과하고, 오류는 한참 뒤
# Discord 의 404(code 10015)로만 드러났다.
GLUED = "https://discord.com/api/webhooks/" + DISCORD_WEBHOOK


def test_discord_rejects_two_urls_glued_together(monkeypatch, caplog):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", GLUED)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.discord_enabled() is False
        assert alert_channels.send_discord("hi") is False

    assert "DISCORD_WEBHOOK_URL" in caplog.text
    assert "두 개" in caplog.text, "무엇이 잘못됐는지 알려주지 않는다"
    # 잘못된 값도 비밀일 수 있다 — 토큰이 로그에 남으면 안 된다.
    assert DISCORD_WEBHOOK.rsplit("/", 1)[-1] not in caplog.text


def test_slack_rejects_two_urls_glued_together(monkeypatch, caplog):
    """같은 오염은 Slack 쪽에서도 난다 — 이 검사는 벤더 공통이다."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/" + WEBHOOK)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.slack_enabled() is False
    assert "두 개" in caplog.text


@pytest.mark.parametrize("bad, expect", [
    (DISCORD_WEBHOOK + "/extra", "조각"),                    # 경로 조각이 하나 더
    (DISCORD_WEBHOOK.rsplit("/", 1)[0], "조각"),             # 토큰 누락
    ("https://discord.com/api/webhooks/abc/" + "t" * 68, "숫자"),  # id 가 숫자가 아님
    # 값 **안쪽**에 공백 (앞뒤 공백은 strip 이 처리하므로 여기서 볼 대상이 아니다)
    ("https://discord.com/api/webhooks/" + "1" * 19 + "/" + "d" * 30 + " " + "d" * 37,
     "공백"),
])
def test_discord_path_shape_is_validated(monkeypatch, caplog, bad, expect):
    """공식 라우트는 POST /webhooks/{webhook.id}/{webhook.token} 이고 id 는 snowflake.

    (webhook.mdx L207 · L23, reference.mdx L136)
    """
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", bad)

    with caplog.at_level(logging.WARNING):
        assert alert_channels.discord_enabled() is False
    assert expect in caplog.text


def test_valid_discord_url_still_passes(discord):
    """검사를 조인 만큼, 정상 URL 을 막지 않는 것도 같이 잠근다."""
    assert alert_channels.discord_enabled() is True


def test_legacy_host_still_passes_structure_check(monkeypatch):
    monkeypatch.setenv(
        "DISCORD_WEBHOOK_URL",
        "https://discordapp.com/api/webhooks/" + "1" * 19 + "/" + "t" * 68,
    )
    assert alert_channels.discord_enabled() is True


def test_query_string_does_not_break_path_check(monkeypatch):
    """사용자가 쿼리를 붙여 둔 URL 도 경로 검사를 통과해야 한다(send 가 wait 을 병합한다)."""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK + "?thread_id=123")
    assert alert_channels.discord_enabled() is True
