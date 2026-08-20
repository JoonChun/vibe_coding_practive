"""/api/alerts/* 라우트 — 특히 테스트 발송의 동시성 가드.

`POST /api/alerts/test` 는 `def`(동기) 핸들러라 FastAPI 가 anyio 스레드풀로 넘긴다.
한 호출이 Slack 15초 + SMTP 30초를 **순차로** 블로킹하며 토큰 1개를 최대 45초 점유하므로,
기본 40토큰이 소진되면 모든 동기 엔드포인트(/api/health · /api/watchlist · /api/paper/* ·
/api/market/status · /api/stocks/search …)가 함께 멈춘다.
"""
import threading

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "t.db"))
    db_module.init_db()

    import server.main as main

    return TestClient(main.app)


@pytest.fixture
def slack_only(monkeypatch):
    import alert_channels
    import notifier

    monkeypatch.setattr(notifier, "email_enabled", lambda: False)
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: True)


def test_config_exposes_no_secrets(client):
    body = client.get("/api/alerts/config").json()

    serialized = str(body)
    assert "hooks.slack.com" not in serialized
    assert "SLACK_WEBHOOK_URL" not in serialized
    assert set(body) >= {"enabled", "channels", "views", "in_window", "baselines"}


def test_test_send_reports_missing_channels(client):
    body = client.post("/api/alerts/test").json()

    assert body["channels"] == []
    assert "SLACK_WEBHOOK_URL" in body["detail"]


def test_test_send_succeeds(client, slack_only, monkeypatch):
    import alert_channels

    sent = []
    monkeypatch.setattr(alert_channels, "send_slack", lambda text, **k: sent.append(text) or True)

    body = client.post("/api/alerts/test").json()

    assert body["results"] == {"slack": True}
    assert "[테스트]" in sent[0]


def test_test_send_does_not_touch_baselines(client, slack_only, monkeypatch):
    import alert_channels

    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)
    client.post("/api/alerts/test")

    assert client.get("/api/alerts/state").json()["items"] == []


def test_concurrent_test_send_is_rejected_with_429(client, slack_only, monkeypatch):
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
        first["response"] = client.post("/api/alerts/test")

    thread = threading.Thread(target=call_first, daemon=True)
    thread.start()
    assert entered.wait(timeout=10), "첫 호출이 발송 단계에 도달하지 않았다"

    second = client.post("/api/alerts/test")

    assert second.status_code == 429
    assert second.headers.get("Retry-After") == "45"
    assert "진행 중" in second.json()["detail"]

    release.set()
    thread.join(timeout=10)
    assert first["response"].status_code == 200


def test_guard_is_released_after_a_failed_send(client, slack_only, monkeypatch):
    """예외가 나도 세마포어를 반납해야 한다 — 안 하면 이후 모든 테스트 발송이 429 로 막힌다."""
    import alert_channels

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(alert_channels, "send_slack", boom)
    with pytest.raises(RuntimeError):
        client.post("/api/alerts/test")

    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)
    assert client.post("/api/alerts/test").status_code == 200
