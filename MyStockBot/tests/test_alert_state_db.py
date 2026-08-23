"""알림 기준선의 SQLite 계층 — 실제 DB로 검증한다.

`tests/test_alerts.py` 는 전부 `_FakeDb` 를 쓰므로 SQL 자체는 한 번도 실행되지 않았다.
여기서 확증된 결함 세 가지를 실 DB로 잠근다:
  · 수집 사이클 중 관심종목 삭제 → 기준선 부활 (WHERE EXISTS 로 구조적 차단)
  · 무음 시딩이 notified_at·source 를 지우는지 (COALESCE)
  · fund_mask 비트마스크가 bool 로 접히는지
그리고 구버전 스키마(fund_present)에서의 마이그레이션.
"""
from datetime import datetime, timezone

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    """임시 DB로 초기화된 db 모듈.

    db.py 는 import 시점에 DB_PATH 를 바인딩하므로 config 가 아니라 **db.DB_PATH** 를
    monkeypatch 해야 한다.
    """
    import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "t.db"))
    db_module.init_db()
    return db_module


def _row(code="005930", kind="long", view="관망", mask=0b111, source="kis", notified=False):
    return {
        "code": code, "view_kind": kind, "view": view,
        "fund_mask": mask, "source": source, "notified": notified,
    }


# ── 활성 관심종목만 기준선을 갖는다 (수집 사이클 vs 삭제 레이스) ──

def test_upsert_is_blocked_for_unknown_code(db):
    """관심종목에 없는 코드는 기준선을 만들 수 없다."""
    assert db.upsert_decision_alert_state([_row()]) == 1  # 반영 시도 건수
    assert db.get_decision_alert_state() == {}, "관심종목에 없는 코드의 기준선이 생겼다"


def test_upsert_works_for_active_code(db):
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row()])

    state = db.get_decision_alert_state()
    assert state[("005930", "long")]["view"] == "관망"


def test_deleted_code_baseline_cannot_be_resurrected(db):
    """수집 사이클은 시작 시점 목록으로 돌고 **끝**에 기준선을 쓴다.

    그 사이에 라우터 스레드가 종목을 지우면, 예전에는 방금 지운 기준선이 되살아났다.
    그 행은 notified_at=NULL 이라 쿨다운도 안 걸려 재추가 시 헛알림이 됐다.
    """
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row()])
    assert db.get_decision_alert_state()

    db.remove_watchlist_item("005930")           # 사이클 진행 중 삭제
    db.upsert_decision_alert_state([_row(view="매수")])   # 낡은 목록으로 사이클 마무리

    assert db.get_decision_alert_state() == {}, "삭제된 종목의 기준선이 부활했다"


def test_readd_starts_from_a_clean_baseline(db):
    """재추가 시점은 경합이 없는 지점 — 여기서 한 번 더 지워 확실히 비운다."""
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row(view="매도", notified=True)])
    db.remove_watchlist_item("005930")
    db.add_watchlist_item("005930", "삼성전자")   # 재활성 경로(soft delete 라 행 재사용)

    assert db.get_decision_alert_state() == {}, "재추가 후에도 옛 기준선이 남았다"


def test_orphan_baselines_are_swept_on_init(db, monkeypatch, tmp_path):
    """이미 부활해 남아 있는 고아 행을 부팅 때 쓸어낸다."""
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row()])
    # watchlist 만 직접 비워 고아 상태를 만든다(부활한 행과 같은 모양).
    conn = db.get_connection()
    conn.execute("DELETE FROM watchlist")
    conn.commit()
    conn.close()
    assert db.get_decision_alert_state()   # 아직 남아 있다

    db.init_db()

    assert db.get_decision_alert_state() == {}


# ── COALESCE 보존 ──

def test_silent_seed_preserves_notified_at(db):
    """무음 시딩이 발송 시각을 밀면 쿨다운 기준이 뒤로 밀려 실제 알림이 지연된다."""
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row(view="매수", notified=True)])
    first = db.get_decision_alert_state()[("005930", "long")]["notified_at"]
    assert first is not None

    db.upsert_decision_alert_state([_row(view="강력매수", notified=False)])
    row = db.get_decision_alert_state()[("005930", "long")]

    assert row["notified_at"] == first
    assert row["view"] == "강력매수"


def test_unknown_source_does_not_erase_stored_source(db):
    """재시작 사이클(출처 불명 → None)이 저장된 'kis' 를 지우면, 다음 사이클에
    NULL→'kis' 가 또 입력 변화로 잡혀 2차 무음 재시딩이 난다."""
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row(source="kis", notified=True)])

    db.upsert_decision_alert_state([_row(source=None, notified=False)])

    assert db.get_decision_alert_state()[("005930", "long")]["source"] == "kis"


# ── 비트마스크가 bool 로 접히지 않는다 ──

@pytest.mark.parametrize("mask", [0, 0b001, 0b010, 0b100, 0b110, 0b111])
def test_fund_mask_round_trips(db, mask):
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row(mask=mask)])

    assert db.get_decision_alert_state()[("005930", "long")]["fund_mask"] == mask


# ── 구버전 스키마 마이그레이션 ──

def test_legacy_fund_present_schema_is_replaced(tmp_path, monkeypatch):
    """CREATE TABLE IF NOT EXISTS 는 컬럼을 추가하지 않으므로 교체가 필요하다.

    두 컬럼의 의미가 달라(0/1 vs 0~7 비트마스크) 값을 옮길 수 없다. 이 테이블은
    "무엇을 마지막으로 알렸는지"만 담은 캐시라 버려도 손실은 무음 시딩 1회다.
    """
    import sqlite3

    import db as db_module

    path = tmp_path / "legacy.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(path))

    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE decision_alert_state (code TEXT NOT NULL, view_kind TEXT NOT NULL, "
        "view TEXT NOT NULL, fund_present INTEGER NOT NULL DEFAULT 0, source TEXT, "
        "notified_at TEXT, updated_at TEXT NOT NULL, PRIMARY KEY (code, view_kind))"
    )
    conn.execute(
        "INSERT INTO decision_alert_state VALUES ('005930','long','매수',1,'kis',NULL,'x')"
    )
    conn.commit()
    conn.close()

    db_module.init_db()

    columns = set()
    conn = db_module.get_connection()
    try:
        for row in conn.execute("PRAGMA table_info(decision_alert_state)"):
            columns.add(row["name"])
    finally:
        conn.close()

    assert "fund_mask" in columns
    assert "fund_present" not in columns
    assert db_module.get_decision_alert_state() == {}


def test_migration_is_idempotent_and_keeps_data(db):
    """이미 신 스키마면 부팅마다 지우지 않아야 한다."""
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row(notified=True)])

    db.init_db()
    db.init_db()

    assert ("005930", "long") in db.get_decision_alert_state()


# ── 통합: 실 DB 로 돈 process_cycle 이 삭제된 종목을 되살리지 않는다 ──

def test_process_cycle_with_real_db_respects_deletion(db, monkeypatch):
    import alert_channels
    import decision_rules as dr
    import notifier
    from server.services import alerts

    monkeypatch.setattr(alerts, "DECISION_ALERT_ENABLED", True)
    monkeypatch.setattr(alerts, "DECISION_ALERT_VIEWS", ("long",))
    monkeypatch.setattr(alerts, "DECISION_ALERT_CONFIRM_CYCLES", 1)
    monkeypatch.setattr(alerts, "DECISION_ALERT_COOLDOWN_MINUTES", 0)
    monkeypatch.setattr(alerts, "_pending", {})
    monkeypatch.setattr(notifier, "email_enabled", lambda: False)
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: True)
    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)

    item = {
        "code": "005930", "name": "삼성전자", "long_view": dr.VIEW_BUY, "short_view": None,
        "per": 12.0, "pbr": 1.2, "roe": 11.0, "source": "kis", "source_60m": "kis",
        "close": 71200.0, "change_pct": 1.0,
    }
    now = datetime(2026, 7, 24, 11, 0, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Seoul"))

    db.add_watchlist_item("005930", "삼성전자")
    alerts.process_cycle([item], now)                 # 시딩
    assert db.get_decision_alert_state()

    db.remove_watchlist_item("005930")
    item["long_view"] = dr.VIEW_SELL
    alerts.process_cycle([item], now)                 # 낡은 items 로 사이클 마무리

    assert db.get_decision_alert_state() == {}


def test_utc_timestamps_are_written(db):
    """_parse_ts 가 UTC naive 문자열을 기대한다 — 로컬 시각을 쓰면 TTL·쿨다운이 9시간 어긋난다."""
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_decision_alert_state([_row(notified=True)])

    written = db.get_decision_alert_state()[("005930", "long")]["notified_at"]
    parsed = datetime.strptime(written, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    assert abs((datetime.now(timezone.utc) - parsed).total_seconds()) < 120
