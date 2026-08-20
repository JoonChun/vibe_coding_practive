"""판정 전환 알림 — 오알림 경로를 하나씩 잠근다.

이 기능의 실패 모드는 "알림이 안 온다"가 아니라 "쓸모없는 알림이 계속 온다"다.
아래 테스트는 server/services/alerts.py 상단 ①~⑧ 게이트에 1:1로 대응한다.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import alert_channels
import decision_rules as dr
import notifier
from server.services import alerts

KST = ZoneInfo("Asia/Seoul")

# 2026-07-24(금) 11:00 KST — 거래일 정규장 안(하드코딩 표 기준 평일·비휴일).
NOW = datetime(2026, 7, 24, 11, 0, tzinfo=KST)


def _item(code="005930", name="삼성전자", *, short=None, long=None,
          per=12.0, source="kis", source_60m="kis", close=71200.0, change_pct=1.83):
    return {
        "code": code, "name": name,
        "short_view": short, "long_view": long,
        "per": per, "pbr": 1.2, "roe": 11.0,
        "source": source, "source_60m": source_60m,
        "close": close, "change_pct": change_pct,
    }


def _state(view, *, kind="long", fund_present=1, source="kis",
           notified_at=NOW, updated_at=NOW):
    def _ts(v):
        if v is None:
            return None
        return v.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    return {("005930", kind): {
        "view": view, "fund_present": fund_present, "source": source,
        "notified_at": _ts(notified_at), "updated_at": _ts(updated_at),
    }}


def _diff(items, state, pending=None, now=NOW, **kwargs):
    kwargs.setdefault("kinds", ("long",))
    kwargs.setdefault("side_only", True)
    kwargs.setdefault("confirm_cycles", 1)
    kwargs.setdefault("cooldown_minutes", 0)
    kwargs.setdefault("state_ttl_days", 7)
    return alerts.diff(items, state, pending or {}, now, **kwargs)


# ── ① 판정 없음은 알리지 않고 기준선도 건드리지 않는다 ──

@pytest.mark.parametrize("view", [None, dr.NO_DATA])
def test_no_data_is_never_an_alert(view):
    """수집 실패(_error_item 은 판정을 None 으로 채운다)가 매매 신호로 보이면 안 된다."""
    transitions, seeds, pending = _diff([_item(long=view)], _state(dr.VIEW_BUY))

    assert transitions == []
    assert seeds == [], "판정 없음으로 기준선을 옮겼다 — 복구 시 가짜 전환이 생긴다"
    assert pending == {}


def test_recovery_from_no_data_to_same_view_is_silent():
    """데이터부족 사이클이 기준선을 건드리지 않았으므로, 복구되면 '변화 없음'이 된다."""
    state = _state(dr.VIEW_BUY)
    _diff([_item(long=dr.NO_DATA)], state)          # 결측 사이클
    transitions, _, _ = _diff([_item(long=dr.VIEW_BUY)], state)   # 복구

    assert transitions == []


# ── ② 기준선은 '마지막으로 알린 판정' — 부팅 폭발·왕복 플랩 방지 ──

def test_first_sight_seeds_silently():
    """기준선이 없으면 알리지 않고 조용히 심는다 — 부팅 직후 전 종목 알림 방지."""
    transitions, seeds, _ = _diff([_item(long=dr.VIEW_BUY)], {})

    assert transitions == []
    assert seeds == [{
        "code": "005930", "view_kind": "long", "view": dr.VIEW_BUY,
        "fund_present": 1, "source": "kis", "notified": False,
    }]


def test_round_trip_back_to_notified_view_is_silent():
    """매수→매도로 알린 뒤 매수로 되돌아오면, 마지막 알린 값과 같으므로 알리지 않는다."""
    transitions, _, _ = _diff([_item(long=dr.VIEW_BUY)], _state(dr.VIEW_BUY))

    assert transitions == []


def test_stale_baseline_is_reseeded_not_alerted():
    """관심종목에서 뺐다가 한참 뒤 다시 넣은 경우 — 옛 기준선과 비교하지 않는다."""
    old = NOW - timedelta(days=30)
    state = _state(dr.VIEW_BUY, notified_at=old, updated_at=old)

    transitions, seeds, _ = _diff([_item(long=dr.VIEW_SELL)], state, state_ttl_days=7)

    assert transitions == []
    assert seeds[0]["view"] == dr.VIEW_SELL


# ── ③ 입력 구성이 바뀐 사이클은 알리지 않는다 ──

def test_late_arriving_financials_do_not_alert():
    """재무 6시간 캐시가 부팅 몇 사이클 뒤 채워지면 장기 판정이 ±3점 통째로 움직인다.

    '첫 사이클을 기준선으로' 만으로는 막히지 않는 경로 — 2~3번째 사이클에 터진다.
    """
    state = _state(dr.VIEW_HOLD, fund_present=0)
    item = _item(long=dr.VIEW_STRONG_BUY, per=8.0)  # 재무 도착

    transitions, seeds, _ = _diff([item], state)

    assert transitions == []
    assert seeds[0] == {
        "code": "005930", "view_kind": "long", "view": dr.VIEW_STRONG_BUY,
        "fund_present": 1, "source": "kis", "notified": False,
    }


def test_source_switch_does_not_alert():
    """kis↔yfinance 로 출처가 바뀌면 라벨이 바뀔 수 있다 — 시장이 아니라 입력이 바뀐 것."""
    state = _state(dr.VIEW_BUY, source="kis")
    item = _item(long=dr.VIEW_SELL, source="yfinance")

    transitions, seeds, _ = _diff([item], state)

    assert transitions == []
    assert seeds[0]["source"] == "yfinance"


def test_alerts_again_once_context_is_stable():
    """구성 변화로 한 사이클 참았을 뿐, 안정되면 다음 전환은 정상적으로 알린다."""
    state = _state(dr.VIEW_BUY, source="yfinance")
    transitions, _, _ = _diff([_item(long=dr.VIEW_SELL, source="yfinance")], state)

    assert [t.after for t in transitions] == [dr.VIEW_SELL]


# ── ④ 측이 바뀔 때만 알린다 (골든크로스의 구조적 강등) ──

def test_strong_buy_to_buy_is_not_an_alert():
    """골든크로스(+2)는 다음 봉에 진입구간(+1)으로 내려앉는다 — 시장 사건이 아니다."""
    transitions, seeds, _ = _diff([_item(long=dr.VIEW_BUY)], _state(dr.VIEW_STRONG_BUY))

    assert transitions == []
    # 다만 기준선은 최신 라벨로 옮겨, 다음 알림의 '이전 판정'이 실제 직전 값이 되게 한다.
    assert seeds[0]["view"] == dr.VIEW_BUY


def test_hold_to_strong_buy_crosses_sides_and_alerts():
    transitions, _, _ = _diff([_item(long=dr.VIEW_STRONG_BUY)], _state(dr.VIEW_HOLD))

    assert len(transitions) == 1
    t = transitions[0]
    assert (t.before, t.after, t.kind) == (dr.VIEW_HOLD, dr.VIEW_STRONG_BUY, "long")
    assert (t.close, t.change_pct) == (71200.0, 1.83)


def test_sell_to_strong_sell_is_not_an_alert():
    """매도측 대칭 — 데드크로스도 다음 봉에 매도구간으로 내려앉는다."""
    transitions, _, _ = _diff([_item(long=dr.VIEW_STRONG_SELL)], _state(dr.VIEW_SELL))

    assert transitions == []


def test_side_only_off_reports_grade_changes():
    transitions, _, _ = _diff(
        [_item(long=dr.VIEW_BUY)], _state(dr.VIEW_STRONG_BUY), side_only=False
    )

    assert [(t.before, t.after) for t in transitions] == [(dr.VIEW_STRONG_BUY, dr.VIEW_BUY)]


# ── ⑤ 히스테리시스 ──

def test_confirm_cycles_delays_until_view_holds():
    state = _state(dr.VIEW_HOLD)
    item = [_item(long=dr.VIEW_BUY)]

    transitions, _, pending = _diff(item, state, confirm_cycles=2)
    assert transitions == []
    assert pending[("005930", "long")] == {"view": dr.VIEW_BUY, "count": 1}

    transitions, _, pending = _diff(item, state, pending, confirm_cycles=2)
    assert len(transitions) == 1


def test_flapping_within_confirm_window_never_fires():
    """매수↔매도로 흔들리면 카운터가 리셋되어 아무것도 확정되지 않는다."""
    state = _state(dr.VIEW_HOLD)
    pending = {}
    for view in (dr.VIEW_BUY, dr.VIEW_SELL, dr.VIEW_BUY, dr.VIEW_SELL):
        transitions, _, pending = _diff([_item(long=view)], state, pending, confirm_cycles=2)
        assert transitions == []


def test_returning_to_baseline_clears_the_counter():
    state = _state(dr.VIEW_HOLD)
    _, _, pending = _diff([_item(long=dr.VIEW_BUY)], state, confirm_cycles=3)
    assert pending

    _, _, pending = _diff([_item(long=dr.VIEW_HOLD)], state, pending, confirm_cycles=3)
    assert pending == {}, "기준선으로 돌아왔는데 카운터가 남아 있다"


# ── ⑥ 쿨다운 ──

def test_cooldown_suppresses_but_keeps_the_counter():
    state = _state(dr.VIEW_HOLD, notified_at=NOW - timedelta(minutes=10))

    transitions, _, pending = _diff(
        [_item(long=dr.VIEW_BUY)], state, cooldown_minutes=60
    )
    assert transitions == []
    # 쿨다운이 풀리는 즉시 발화해야 하므로 카운터는 유지된다.
    assert pending[("005930", "long")]["count"] == 1

    later = NOW + timedelta(minutes=55)
    transitions, _, _ = _diff(
        [_item(long=dr.VIEW_BUY)], state, pending, now=later, cooldown_minutes=60
    )
    assert len(transitions) == 1


def test_never_notified_baseline_has_no_cooldown():
    """무음 시딩된 기준선(notified_at=None)은 쿨다운이 없다 — 첫 전환을 늦추지 않는다."""
    state = _state(dr.VIEW_HOLD, notified_at=None)

    transitions, _, _ = _diff([_item(long=dr.VIEW_BUY)], state, cooldown_minutes=60)

    assert len(transitions) == 1


# ── ⑦ 장 시간대 게이트 ──

@pytest.mark.parametrize("moment,expected", [
    (datetime(2026, 7, 24, 8, 59, tzinfo=KST), False),   # 장전
    (datetime(2026, 7, 24, 9, 0, tzinfo=KST), True),
    (datetime(2026, 7, 24, 15, 30, tzinfo=KST), True),
    (datetime(2026, 7, 24, 15, 31, tzinfo=KST), False),  # 마감 후
    (datetime(2026, 7, 26, 11, 0, tzinfo=KST), False),   # 일요일
    (datetime(2026, 9, 25, 11, 0, tzinfo=KST), False),   # 추석 연휴
])
def test_alert_window(moment, expected):
    """유휴 사이클(600초) > 60분봉 신선도(300초) 라서 주말에도 재조회가 돈다.

    게이트가 없으면 야후 실패→복구가 일요일 새벽 알림이 된다.
    """
    assert alerts.in_alert_window(moment) is expected


# ── 단기·장기 동시 감시 ──

def test_short_and_long_are_tracked_independently():
    state = {**_state(dr.VIEW_HOLD, kind="long"),
             **_state(dr.VIEW_HOLD, kind="short", fund_present=0)}
    item = _item(long=dr.VIEW_BUY, short=dr.VIEW_SELL)

    transitions, _, _ = _diff([item], state, kinds=("short", "long"))

    assert {(t.kind, t.after) for t in transitions} == {
        ("short", dr.VIEW_SELL), ("long", dr.VIEW_BUY),
    }


def test_short_kind_uses_source_60m_for_context():
    """단기 판정의 출처는 source_60m 이다 — 일봉 출처로 비교하면 오탐이 난다."""
    state = _state(dr.VIEW_HOLD, kind="short", fund_present=0, source="kis")
    item = _item(short=dr.VIEW_BUY, source="yfinance", source_60m="kis")

    transitions, _, _ = _diff([item], state, kinds=("short",))

    assert len(transitions) == 1, "일봉 출처 변화가 단기 알림을 막았다"


# ── ⑧ 발송 실패 시 기준선을 옮기지 않는다 (process_cycle 통합) ──

class _FakeDb:
    def __init__(self, state=None):
        self.state = state or {}
        self.upserts = []

    def get_decision_alert_state(self):
        return dict(self.state)

    def upsert_decision_alert_state(self, rows):
        self.upserts.extend(rows)
        return len(rows)


@pytest.fixture
def wired(monkeypatch):
    """process_cycle 을 실제 DB·네트워크 없이 돌린다."""
    fake_db = _FakeDb(_state(dr.VIEW_HOLD))
    monkeypatch.setattr(alerts, "db", fake_db)
    monkeypatch.setattr(alerts, "DECISION_ALERT_ENABLED", True)
    monkeypatch.setattr(alerts, "DECISION_ALERT_VIEWS", ("long",))
    monkeypatch.setattr(alerts, "DECISION_ALERT_CONFIRM_CYCLES", 1)
    monkeypatch.setattr(alerts, "DECISION_ALERT_COOLDOWN_MINUTES", 0)
    monkeypatch.setattr(alerts, "_pending", {})
    monkeypatch.setattr(notifier, "email_enabled", lambda: False)
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: True)
    return fake_db


def test_failed_send_does_not_move_the_baseline(monkeypatch, wired):
    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: False)

    result = alerts.process_cycle([_item(long=dr.VIEW_BUY)], NOW)

    assert result["sent"] == 0
    assert result["transitions"] == 1
    assert wired.upserts == [], "발송에 실패했는데 기준선을 옮겼다 — 그 전환은 영구 유실된다"
    assert alerts._pending[("005930", "long")]["count"] == 1, "재시도용 카운터가 사라졌다"


def test_successful_send_commits_and_clears_pending(monkeypatch, wired):
    sent = []
    monkeypatch.setattr(alert_channels, "send_slack", lambda text, **k: sent.append(text) or True)

    result = alerts.process_cycle([_item(long=dr.VIEW_BUY)], NOW)

    assert result["sent"] == 1
    assert wired.upserts == [{
        "code": "005930", "view_kind": "long", "view": dr.VIEW_BUY,
        "fund_present": 1, "source": "kis", "notified": True,
    }]
    assert alerts._pending == {}
    assert "매수" in sent[0]


def test_disabled_flag_short_circuits(monkeypatch, wired):
    monkeypatch.setattr(alerts, "DECISION_ALERT_ENABLED", False)
    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)

    result = alerts.process_cycle([_item(long=dr.VIEW_BUY)], NOW)

    assert result == {"enabled": False, "reason": "DECISION_ALERT_ENABLED 미설정", "sent": 0}
    assert wired.upserts == []


def test_no_channel_configured_leaves_state_untouched(monkeypatch, wired):
    """채널을 나중에 붙였을 때 전 종목 알림이 터지지 않도록, 그 전에는 시딩도 하지 않는다."""
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: False)

    result = alerts.process_cycle([_item(long=dr.VIEW_BUY)], NOW)

    assert result["sent"] == 0 and result["channels"] == []
    assert wired.upserts == []


def test_outside_window_sends_nothing(monkeypatch, wired):
    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)
    sunday = datetime(2026, 7, 26, 3, 0, tzinfo=KST)

    result = alerts.process_cycle([_item(long=dr.VIEW_BUY)], sunday)

    assert result["reason"] == "장 시간 외"
    assert wired.upserts == []


def test_seeds_are_committed_even_without_transitions(monkeypatch, wired):
    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)

    result = alerts.process_cycle([_item(code="000660", name="SK하이닉스", long=dr.VIEW_BUY)], NOW)

    assert result["sent"] == 0
    assert [r["code"] for r in wired.upserts] == ["000660"]
    assert wired.upserts[0]["notified"] is False


# ── 스레드·유량 안전 (사이클을 늘리거나 서버를 멈추지 않는다) ──

def test_dispatch_never_touches_the_collector_state_lock(monkeypatch, wired):
    """collector._state_lock 은 이벤트 루프 스레드가 잡는다 — 알림 경로가 쥐면 서버가 멈춘다."""
    from server.services import collector

    observed = []

    def fake_send(text, **kwargs):
        acquired = collector._state_lock.acquire(blocking=False)
        observed.append(acquired)
        if acquired:
            collector._state_lock.release()
        return True

    monkeypatch.setattr(alert_channels, "send_slack", fake_send)
    alerts.process_cycle([_item(long=dr.VIEW_BUY)], NOW)

    assert observed == [True], "발송 중 _state_lock 이 잡혀 있었다"


def test_alert_path_never_calls_kis(monkeypatch, wired):
    """kis_auth.kis_throttle() 은 전역 락을 잡고 0.5초 sleep 한다 — 알림이 부르면 사이클이 늘어난다."""
    import kis_auth

    calls = []
    monkeypatch.setattr(kis_auth, "kis_throttle", lambda: calls.append(1))
    monkeypatch.setattr(kis_auth, "get_token", lambda: calls.append(1))
    monkeypatch.setattr(alert_channels, "send_slack", lambda *a, **k: True)

    alerts.process_cycle([_item(long=dr.VIEW_BUY)], NOW)

    assert calls == []


# ── 렌더링 ──

def test_slack_text_uses_single_asterisk_bold():
    """Slack mrkdwn 의 굵게는 `*bold*` 다. `**bold**` 는 별표가 그대로 보인다."""
    t = alerts.Transition("005930", "삼성전자", "long", dr.VIEW_HOLD, dr.VIEW_BUY, 71200.0, 1.83)
    text = alerts.render_slack_text([t], NOW)

    assert "**" not in text
    assert "*삼성전자*(005930) 장기 관망 → *매수*" in text
    assert "71,200원 (+1.83%)" in text
    assert "닫히지 않은 봉" in text, "장중 판정의 한계 문구가 빠졌다"


def test_slack_text_truncates_but_reports_the_total(monkeypatch):
    monkeypatch.setattr(alerts, "DECISION_ALERT_MAX_ROWS", 2)
    ts = [
        alerts.Transition(f"00000{i}", f"종목{i}", "long", dr.VIEW_HOLD, dr.VIEW_BUY, None, None)
        for i in range(5)
    ]
    text = alerts.render_slack_text(ts, NOW)

    assert "판정 전환* 5건" in text
    assert "외 3건" in text


def test_email_escapes_stock_names():
    """종목명은 시트·외부 API 에서 오므로 검증되지 않은 문자열이다."""
    t = alerts.Transition(
        "005930", "<script>x</script>", "long", dr.VIEW_HOLD, dr.VIEW_BUY, None, None
    )
    _, html_body = alerts.render_email([t], NOW)

    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body


def test_missing_price_renders_without_crashing():
    t = alerts.Transition("005930", "삼성전자", "short", dr.VIEW_BUY, dr.VIEW_SELL, None, None)

    assert "삼성전자" in alerts.render_slack_text([t], NOW)
    subject, html_body = alerts.render_email([t], NOW)
    assert "판정 전환 1건" in subject
    assert "단기" in html_body
