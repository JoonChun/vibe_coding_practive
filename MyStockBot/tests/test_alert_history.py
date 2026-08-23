"""알림 이력 — **실제로 발송된 전환만** 남긴다.

## 왜 이력이 필요한가
`decision_alert_state` 는 "마지막으로 알린 판정" 하나만 들고 있다. 그래서 "이 종목 판정이
언제 어떻게 바뀌었나"에 답할 수 없다 — 알림을 놓쳤거나 지난 며칠을 되짚고 싶을 때
복원할 경로가 없었다.

## 왜 "발송된 것만" 인가
쿨다운·히스테리시스로 눌린 전환은 `_pending` 에 남아 조건이 풀리면 발화한다 — 유실이
아니라 지연이다. 그것까지 이력에 넣으면 같은 전환이 두 번 보이고, "안 왔다"와 "아직
안 왔다"를 구분할 수 없게 된다. 이력의 정의는 **"알림으로 나간 것"** 이다.

또한 테스트 발송(`POST /api/alerts/test`)은 가짜 전환이므로 이력에 남지 않아야 한다.
남으면 이력이 실제 시장 이벤트의 기록이 아니게 된다.
"""
import pytest

import db as db_module
from server.services import alerts


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "hist.db"))
    db_module.init_db()
    return db_module


def _row(code="005930", after="매수", kind="long"):
    return {
        "code": code, "name": "삼성전자", "view_kind": kind,
        "before_view": "관망", "after_view": after,
        "close": 71200.0, "change_pct": 1.83, "channels": "discord",
    }


# ── 저장·조회 ──

def test_insert_and_read_back(db):
    db.insert_decision_alert_history([_row()])

    items = db.get_decision_alert_history()
    assert len(items) == 1
    row = items[0]
    assert (row["code"], row["view_kind"]) == ("005930", "long")
    assert (row["before_view"], row["after_view"]) == ("관망", "매수")
    assert row["close"] == pytest.approx(71200.0)
    assert row["channels"] == "discord"
    assert row["notified_at"], "발송 시각이 비었다"


def test_newest_first(db):
    db.insert_decision_alert_history([_row(code="000001")])
    db.insert_decision_alert_history([_row(code="000002")])
    db.insert_decision_alert_history([_row(code="000003")])

    codes = [r["code"] for r in db.get_decision_alert_history()]
    assert codes == ["000003", "000002", "000001"], "최신순이 아니다"


def test_limit_is_clamped(db):
    db.insert_decision_alert_history([_row(code=f"{i:06d}") for i in range(1, 21)])

    assert len(db.get_decision_alert_history(limit=5)) == 5
    # 음수·0 을 그대로 LIMIT 에 넘기면 SQLite 가 전체를 돌려준다(LIMIT -1 = 무제한).
    assert len(db.get_decision_alert_history(limit=0)) >= 1
    assert len(db.get_decision_alert_history(limit=-3)) >= 1


def test_empty_insert_is_a_noop(db):
    db.insert_decision_alert_history([])
    assert db.get_decision_alert_history() == []


def test_multiple_rows_in_one_call(db):
    db.insert_decision_alert_history([_row(code="000001"), _row(code="000002")])
    assert len(db.get_decision_alert_history()) == 2


# ── 보존 상한 ──

def test_retention_prunes_oldest(db, monkeypatch):
    """개인용 앱이라 이력이 무한히 자라면 DB 만 커진다. 오래된 것부터 지운다."""
    monkeypatch.setattr(db_module, "ALERT_HISTORY_MAX_ROWS", 10)

    for i in range(1, 26):
        db.insert_decision_alert_history([_row(code=f"{i:06d}")])

    items = db.get_decision_alert_history(limit=500)
    assert len(items) == 10, f"상한이 지켜지지 않았다: {len(items)}건"
    # 남은 것은 최신 10건이어야 한다.
    assert [r["code"] for r in items][0] == "000025"
    assert [r["code"] for r in items][-1] == "000016"


# ── 엔진 연결 ──

def _snapshot(view="매수"):
    return [{
        "code": "005930", "name": "삼성전자", "close": 71200.0, "change_pct": 1.83,
        "short_view": view, "long_view": view, "source": "kis",
        "factors": {"per": 10.0, "pbr": 1.0, "roe": 15.0},
    }]


@pytest.fixture
def engine(db, monkeypatch):
    """알림 게이트를 열고 발송을 가짜로 바꾼 상태.

    ★ 관심종목을 먼저 등록해야 한다. `upsert_decision_alert_state` 가
    `WHERE EXISTS (SELECT 1 FROM watchlist ...)` 로 보호되어 있어, 등록되지 않은 종목의
    기준선은 저장되지 않는다 — 그러면 매 사이클이 "기준선 없음 → 무음 시딩"만 반복하고
    전환이 절대 발생하지 않는다(이 테스트를 쓰다 실제로 걸렸다).
    """
    db.add_watchlist_item("005930", "삼성전자")
    monkeypatch.setattr(alerts, "DECISION_ALERT_ENABLED", True)
    monkeypatch.setattr(alerts, "DECISION_ALERT_CONFIRM_CYCLES", 1)
    monkeypatch.setattr(alerts, "DECISION_ALERT_COOLDOWN_MINUTES", 0)
    monkeypatch.setattr(alerts, "in_alert_window", lambda _now: True)
    monkeypatch.setattr(alerts, "_pending", {})
    return alerts


def test_history_is_written_on_successful_send(engine, monkeypatch):
    monkeypatch.setattr(engine, "channels", lambda: ["discord"])
    monkeypatch.setattr(engine, "dispatch", lambda *a, **k: {"discord": True})

    engine.process_cycle(_snapshot("관망"))          # 무음 시딩
    engine.process_cycle(_snapshot("매수"))          # 전환 발송

    items = db_module.get_decision_alert_history()
    assert items, "발송했는데 이력이 없다"
    assert items[0]["after_view"] == "매수"
    assert items[0]["channels"] == "discord"


def test_history_is_not_written_when_every_channel_fails(engine, monkeypatch):
    """발송 실패 시 기준선을 옮기지 않는 것과 같은 이유 — 나가지 않은 것은 이력이 아니다."""
    monkeypatch.setattr(engine, "channels", lambda: ["discord"])
    monkeypatch.setattr(engine, "dispatch", lambda *a, **k: {"discord": False})

    engine.process_cycle(_snapshot("관망"))
    engine.process_cycle(_snapshot("매수"))

    assert db_module.get_decision_alert_history() == []


def test_history_records_only_delivered_channels(engine, monkeypatch):
    monkeypatch.setattr(engine, "channels", lambda: ["discord", "email"])
    monkeypatch.setattr(engine, "dispatch",
                        lambda *a, **k: {"discord": True, "email": False})

    engine.process_cycle(_snapshot("관망"))
    engine.process_cycle(_snapshot("매수"))

    items = db_module.get_decision_alert_history()
    assert items
    assert items[0]["channels"] == "discord", "실패한 채널이 이력에 실렸다"


def test_silent_seeding_writes_no_history(engine, monkeypatch):
    """첫 사이클은 조용히 시딩한다 — 알림이 안 나갔으니 이력도 없다."""
    monkeypatch.setattr(engine, "channels", lambda: ["discord"])
    monkeypatch.setattr(engine, "dispatch", lambda *a, **k: {"discord": True})

    engine.process_cycle(_snapshot("매수"))

    assert db_module.get_decision_alert_history() == []


def test_test_send_does_not_write_history(db, monkeypatch):
    """POST /api/alerts/test 는 가짜 전환이다 — 실제 시장 기록을 오염시키면 안 된다."""
    import alert_channels
    import notifier

    from server.routers import alerts as alerts_router

    monkeypatch.setattr(notifier, "email_enabled", lambda: False)
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: True)
    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)

    from fastapi import Response
    body = alerts_router.send_test_alert(Response())

    assert body["results"] == {"slack": True}, body
    assert db.get_decision_alert_history() == [], "테스트 발송이 이력에 남았다"


# ── 라우터 ──

def test_history_endpoint_returns_items(db):
    from server.routers import alerts as alerts_router

    db.insert_decision_alert_history([_row()])
    body = alerts_router.get_alert_history()

    assert len(body["items"]) == 1
    assert body["items"][0]["code"] == "005930"


def test_history_endpoint_matches_the_schema(db):
    from server.routers import alerts as alerts_router
    from server.schemas import AlertHistoryResponse

    db.insert_decision_alert_history([_row(), _row(code="000660")])
    AlertHistoryResponse.model_validate(alerts_router.get_alert_history())
