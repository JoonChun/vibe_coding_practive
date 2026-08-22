"""/api/alerts/* 라우트 — 특히 테스트 발송의 동시성 가드.

`POST /api/alerts/test` 는 `def`(동기) 핸들러라 FastAPI 가 anyio 스레드풀로 넘긴다.
한 호출이 Slack 15초 + SMTP 30초를 **순차로** 블로킹하며 토큰 1개를 최대 45초 점유하므로,
기본 40토큰이 소진되면 모든 동기 엔드포인트(/api/health · /api/watchlist · /api/paper/* ·
/api/market/status · /api/stocks/search …)가 함께 멈춘다.

## TestClient 를 쓰지 않는 이유
`fastapi.testclient` 는 `httpx`(최신 starlette 는 `httpx2`)를 **하드 요구**한다. 둘 다
requirements.txt 에 없어서, 처음에 TestClient 로 쓴 이 파일은 로컬 venv 에 httpx 가
우연히 깔려 있어서만 통과하고 CI 에서는 수집 단계에서 죽었다(RuntimeError).
런타임에 필요 없는 의존성을 테스트 때문에 추가하는 대신 **핸들러를 직접 호출한다** —
세마포어 동작은 오히려 이 방식이 더 정확히 검증된다(스레드 2개로 직접 경합시킨다).
"""
import threading

import pytest
from fastapi import Response

from server.routers import alerts as alerts_router


@pytest.fixture
def db(tmp_path, monkeypatch):
    import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "t.db"))
    db_module.init_db()
    return db_module


@pytest.fixture
def slack_only(monkeypatch):
    import alert_channels
    import notifier

    monkeypatch.setattr(notifier, "email_enabled", lambda: False)
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: True)


@pytest.fixture(autouse=True)
def _fresh_semaphore(monkeypatch):
    """테스트 간 세마포어 상태가 새지 않도록 매번 새로 만든다."""
    monkeypatch.setattr(alerts_router, "_test_lock", threading.Semaphore(1))


# ── 설정·상태 조회 ──

def test_config_exposes_no_secrets(db):
    body = alerts_router.get_alert_config()

    serialized = str(body)
    assert "hooks.slack.com" not in serialized
    assert "SLACK_WEBHOOK_URL" not in serialized
    assert set(body) >= {"enabled", "channels", "views", "in_window", "baselines"}


def test_state_starts_empty(db):
    assert alerts_router.get_alert_state() == {"items": []}


def test_state_reports_stored_baselines(db):
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([{
        "code": "005930", "view_kind": "long", "view": "매수",
        "fund_mask": 0b111, "source": "kis", "notified": True,
    }])

    items = alerts_router.get_alert_state()["items"]

    assert len(items) == 1
    assert items[0]["code"] == "005930"
    assert items[0]["view"] == "매수"
    assert items[0]["notified_at"] is not None


# ── 테스트 발송 ──

def test_test_send_reports_missing_channels(db, monkeypatch):
    import alert_channels
    import notifier

    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: False)
    monkeypatch.setattr(notifier, "email_enabled", lambda: False)

    body = alerts_router.send_test_alert(Response())

    assert body["channels"] == []
    assert "SLACK_WEBHOOK_URL" in body["detail"]


def test_test_send_succeeds(db, slack_only, monkeypatch):
    import alert_channels

    sent = []
    monkeypatch.setattr(alert_channels, "send_slack", lambda text, **k: sent.append(text) or True)

    body = alerts_router.send_test_alert(Response())

    assert body["results"] == {"slack": True}
    assert "[테스트]" in sent[0]


def test_test_send_reports_failure_with_hint(db, slack_only, monkeypatch):
    import alert_channels

    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: False)

    body = alerts_router.send_test_alert(Response())

    assert body["results"] == {"slack": False}
    assert "실패" in body["detail"]


def test_test_send_does_not_touch_baselines(db, slack_only, monkeypatch):
    import alert_channels

    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)
    alerts_router.send_test_alert(Response())

    assert alerts_router.get_alert_state() == {"items": []}


# ── 동시성 가드 ──

def test_concurrent_test_send_is_rejected_with_429(db, slack_only, monkeypatch):
    """두 번째 동시 호출이 스레드풀 토큰을 또 점유하지 않고 즉시 429 로 돌아온다."""
    import alert_channels

    release = threading.Event()
    entered = threading.Event()

    def blocking_send(text, **kwargs):
        entered.set()
        release.wait(timeout=10)
        return True

    monkeypatch.setattr(alert_channels, "send_slack", blocking_send)

    first: dict = {}

    def call_first():
        first["response"] = Response()
        first["body"] = alerts_router.send_test_alert(first["response"])

    thread = threading.Thread(target=call_first, daemon=True)
    thread.start()
    assert entered.wait(timeout=10), "첫 호출이 발송 단계에 도달하지 않았다"

    second_response = Response()
    second_body = alerts_router.send_test_alert(second_response)

    assert second_response.status_code == 429
    assert second_response.headers.get("Retry-After") == "45"
    assert "진행 중" in second_body["detail"]
    assert second_body["results"] == {}, "429 인데 발송을 시도했다"

    release.set()
    thread.join(timeout=10)
    assert first["body"]["results"] == {"slack": True}
    assert first["response"].status_code == 200


def test_guard_is_released_after_a_failed_send(db, slack_only, monkeypatch):
    """예외가 나도 세마포어를 반납해야 한다 — 안 하면 이후 모든 테스트 발송이 429 로 막힌다."""
    import alert_channels

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(alert_channels, "send_slack", boom)
    with pytest.raises(RuntimeError):
        alerts_router.send_test_alert(Response())

    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)
    response = Response()
    body = alerts_router.send_test_alert(response)

    assert response.status_code == 200
    assert body["results"] == {"slack": True}


def test_guard_allows_sequential_sends(db, slack_only, monkeypatch):
    import alert_channels

    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)

    for _ in range(3):
        response = Response()
        alerts_router.send_test_alert(response)
        assert response.status_code == 200


# ── 실패 안내가 실제 로그 태그를 가리키는지 ──

def test_failure_hint_points_at_the_real_log_tag(db, monkeypatch):
    """이메일 실패 안내는 `[email]` 이 아니라 `[notifier]` 여야 한다.

    이메일을 실제로 보내는 주체는 src/notifier.py 이고 그 로그 태그는 `[notifier]` 다.
    `[email]` 태그는 로그에 존재하지 않으므로, 그대로 안내하면 사용자가 없는 태그를
    grep 하며 원인을 못 찾는다.
    """
    import alert_channels
    import notifier

    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: False)
    monkeypatch.setattr(alert_channels, "discord_enabled", lambda: True)
    monkeypatch.setattr(alert_channels, "send_discord", lambda *a, **k: False)
    monkeypatch.setattr(notifier, "email_enabled", lambda: True)
    monkeypatch.setattr(notifier, "send_html", lambda *a, **k: False)

    body = alerts_router.send_test_alert(Response())

    assert body["results"] == {"discord": False, "email": False}
    assert "[notifier]" in body["detail"]
    assert "[email]" not in body["detail"]
    # 웹훅 채널은 채널명 그대로 찍힌다.
    assert "[discord]" in body["detail"]
    # 채널명 자체는 실패 목록에 남아 있어야 한다 — 무엇이 실패했는지는 채널명으로 읽는다.
    assert "email" in body["detail"] and "discord" in body["detail"]
