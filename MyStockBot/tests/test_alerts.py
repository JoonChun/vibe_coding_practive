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


def _state(view, *, kind="long", fund_mask=0b111, source="kis",
           notified_at=NOW, updated_at=NOW):
    def _ts(v):
        if v is None:
            return None
        return v.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    return {("005930", kind): {
        "view": view, "fund_mask": fund_mask, "source": source,
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
        "fund_mask": 0b111, "source": "kis", "notified": False,
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
    state = _state(dr.VIEW_HOLD, fund_mask=0)
    item = _item(long=dr.VIEW_STRONG_BUY, per=8.0)  # 재무 도착

    transitions, seeds, _ = _diff([item], state)

    assert transitions == []
    assert seeds[0] == {
        "code": "005930", "view_kind": "long", "view": dr.VIEW_STRONG_BUY,
        "fund_mask": 0b111, "source": "kis", "notified": False,
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
             **_state(dr.VIEW_HOLD, kind="short", fund_mask=0)}
    item = _item(long=dr.VIEW_BUY, short=dr.VIEW_SELL)

    transitions, _, _ = _diff([item], state, kinds=("short", "long"))

    assert {(t.kind, t.after) for t in transitions} == {
        ("short", dr.VIEW_SELL), ("long", dr.VIEW_BUY),
    }


def test_short_kind_uses_source_60m_for_context():
    """단기 판정의 출처는 source_60m 이다 — 일봉 출처로 비교하면 오탐이 난다."""
    state = _state(dr.VIEW_HOLD, kind="short", fund_mask=0, source="kis")
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
        "fund_mask": 0b111, "source": "kis", "notified": True,
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

def test_collector_calls_alerts_outside_the_state_lock(monkeypatch):
    """collector._run_cycle 이 **락 밖에서** 알림을 부르는지 — 호출부를 실제로 실행해 검증한다.

    이 테스트는 반드시 `collector._run_cycle()` 을 통과해야 한다. 예전 버전은
    `alerts.process_cycle` 을 직접 불러서 **락을 쥔 주체가 애초에 없었고**,
    `acquire(blocking=False)` 가 항상 True 라 위반을 탐지할 수 없었다.
    실측으로 확인: process_cycle 호출을 `with _state_lock:` 안으로 옮겨도 예전 테스트는
    통과했다. 지금 버전은 그 회귀에서 실패한다.

    락 안에서 I/O 를 하면 서버 전체가 멈춘다 — 그 락은 이벤트 루프 스레드가 직접 잡는다
    (routers/snapshot.py 의 async 핸들러가 to_thread 없이 collector.get_state() 호출).
    """
    import db as db_module
    import kis_auth
    from server.services import collector

    # **모든** 호출을 기록한다. 마지막 호출만 보면, 락 안에 호출이 하나 추가돼도 뒤이은
    # 락 밖 호출이 기록을 덮어써서 회귀를 놓친다(실제로 그렇게 새는 것을 확인했다).
    observed: list[bool] = []

    def spy(items, now=None):
        observed.append(collector._state_lock.locked())
        return {"enabled": False, "sent": 0}

    monkeypatch.setattr(db_module, "load_watchlist", lambda: [{"code": "005930", "name": "삼성전자"}])
    monkeypatch.setattr(kis_auth, "get_token", lambda: "tok")
    monkeypatch.setattr(collector, "_collect_one", lambda item, token: _item(long=dr.VIEW_BUY))
    monkeypatch.setattr(collector.alerts, "process_cycle", spy)

    collector._run_cycle()

    assert observed, "collector 가 알림을 호출하지 않았다"
    assert not any(observed), (
        f"_state_lock 을 쥔 채로 알림을 호출했다(호출별 락 상태: {observed}) — 서버가 멈춘다"
    )


def test_alerts_module_itself_never_takes_the_state_lock(monkeypatch, wired):
    """알림 모듈 내부에서 락을 잡는 회귀도 함께 막는다(발송 시점에 락이 비어 있는지)."""
    from server.services import collector

    observed = []

    def fake_send(text, **kwargs):
        observed.append(collector._state_lock.locked())
        return True

    monkeypatch.setattr(alert_channels, "send_slack", fake_send)
    alerts.process_cycle([_item(long=dr.VIEW_BUY)], NOW)

    assert observed == [False], "발송 중 _state_lock 이 잡혀 있었다"


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


def test_slack_text_reports_total_and_deferred_count():
    """렌더러는 자르지 않고, 호출부가 잘라 넘긴 목록 + 전체 건수를 받아 표시만 한다.

    (예전에는 렌더러가 잘랐는데 호출부는 전체로 기준선을 옮겨 꼬리가 유실됐다 —
    test_truncated_tail_is_deferred_not_lost 참고.)
    """
    ts = [
        alerts.Transition(f"00000{i}", f"종목{i}", "long", dr.VIEW_HOLD, dr.VIEW_BUY, None, None)
        for i in range(2)
    ]
    text = alerts.render_slack_text(ts, NOW, total=5)

    assert "판정 전환* 5건" in text
    assert text.count("•") == 2
    assert "나머지 3건은 다음 사이클" in text


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


# ══════════════════════════════════════════════════════════════════════
# 적대적 리뷰(6관점 × 반증 검증)에서 확증된 결함들의 회귀 테스트.
# 전부 "228건이 통과하는데도 틀렸던" 경로다.
# ══════════════════════════════════════════════════════════════════════

# ── 재무 '일부' 도착이 오알림이 되던 경로 (fund_present 1비트 → fund_mask 비트마스크) ──

def test_partial_financial_arrival_does_not_alert():
    """per 만 뒤늦게 도착하는 사이클. 적자·미공시 종목은 per 만 결측인 경우가 흔하다.

    any() 로 접은 1비트로는 이 사이클이 1→1 로 보여 게이트 ③을 그대로 통과했다.
    세 값은 각각 독립적으로 ±1 점을 내고 관망 구간이 score==0 단일 점이라, 한 필드의
    도착만으로도 측이 바뀐다 → 시장이 안 움직였는데 '관망 → 매수'가 나갔다.
    """
    state = _state(dr.VIEW_HOLD, fund_mask=0b110)          # pbr·roe 만 있던 상태
    item = _item(long=dr.VIEW_BUY, per=8.0)                # per 도착 → 0b111

    transitions, seeds, _ = _diff([item], state)

    assert transitions == [], "재무 한 필드 도착이 매매 신호로 나갔다"
    assert seeds[0]["fund_mask"] == 0b111


def test_partial_financial_loss_does_not_alert():
    """역방향 — KIS 가 per 을 빈 값으로 주는 사이클도 대칭으로 막아야 한다."""
    state = _state(dr.VIEW_BUY, fund_mask=0b111)
    item = _item(long=dr.VIEW_HOLD, per=None)              # per 소실 → 0b110

    transitions, seeds, _ = _diff([item], state)

    assert transitions == []
    assert seeds[0]["fund_mask"] == 0b110


def test_context_mask_encodes_each_field_independently():
    assert alerts._context(_item(per=1.0), "long")[0] == 0b111
    assert alerts._context({"per": 1.0}, "long")[0] == 0b001
    assert alerts._context({"pbr": 1.0}, "long")[0] == 0b010
    assert alerts._context({"roe": 1.0}, "long")[0] == 0b100
    assert alerts._context({}, "long")[0] == 0
    # 단기 판정은 재무를 쓰지 않으므로 항상 0
    assert alerts._context(_item(per=1.0), "short")[0] == 0


def test_financials_unchanged_still_alerts_on_real_move():
    """재무 구성이 그대로면 게이트 ③은 침묵해야 한다 — 오알림을 알림 누락으로 바꾸지 않는다."""
    transitions, _, _ = _diff([_item(long=dr.VIEW_SELL)], _state(dr.VIEW_BUY))

    assert [t.after for t in transitions] == [dr.VIEW_SELL]


# ── 재시작 첫 사이클의 "store" 센티널이 전 종목 기준선을 리셋하던 경로 ──

@pytest.mark.parametrize("sentinel", ["store", None, "", "unknown"])
def test_unknown_source_does_not_reseed_everything(sentinel):
    """collector._remembered_source() 는 저장소 서빙 시 실제 출처가 아닌 "store" 를 준다.

    재시작 직후 첫 사이클은 저장소가 신선하므로 **항상** 저장소 서빙이다. 이 값을 영속된
    "kis" 와 비교하면 전 종목·전 view_kind 가 무음 재시딩되어, 장중 재기동 한 번으로
    그 구간의 전환이 전부 사라진다 — 영속화(게이트 ②)의 목적이 통째로 무효화된다.
    """
    state = _state(dr.VIEW_HOLD, source="kis")
    item = _item(long=dr.VIEW_BUY, source=sentinel)

    transitions, seeds, _ = _diff([item], state)

    assert [t.after for t in transitions] == [dr.VIEW_BUY], (
        f"source={sentinel!r} 가 입력 변화로 오인되어 전환이 삼켜졌다"
    )
    assert seeds == []


def test_provenance_keeps_only_real_sources():
    assert alerts._provenance("kis") == "kis"
    assert alerts._provenance("yfinance") == "yfinance"
    assert alerts._provenance("store") is None
    assert alerts._provenance(None) is None


def test_real_source_switch_is_still_gated():
    """알려진 출처끼리 바뀌는 경우는 여전히 게이트 ③이 잡아야 한다."""
    transitions, seeds, _ = _diff(
        [_item(long=dr.VIEW_SELL, source="yfinance")], _state(dr.VIEW_BUY, source="kis")
    )

    assert transitions == []
    assert seeds[0]["source"] == "yfinance"


# ── MAX_ROWS 로 잘린 꼬리가 영구 유실되던 경로 ──

def test_truncated_tail_is_deferred_not_lost(monkeypatch, wired):
    """지수 급락일처럼 알림이 가장 필요한 날에만 터졌던 결함.

    렌더러가 30건만 실어 보냈는데 호출부는 전체 목록으로 기준선을 옮겨서, 어느 채널에도
    실린 적 없는 전환이 '알린 판정'으로 기록되고 다시는 보고되지 않았다(로그도 건수만).
    """
    monkeypatch.setattr(alerts, "DECISION_ALERT_MAX_ROWS", 2)
    sent = []
    monkeypatch.setattr(alert_channels, "send_slack", lambda text, **k: sent.append(text) or True)

    codes = ["00000%d" % i for i in range(3)]
    wired.state = {
        (c, "long"): {
            "view": dr.VIEW_HOLD, "fund_mask": 0b111, "source": "kis",
            "notified_at": None, "updated_at": NOW.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
        for c in codes
    }
    items = [_item(code=c, name=f"종목{c}", long=dr.VIEW_BUY) for c in codes]

    result = alerts.process_cycle(items, NOW)

    assert result["transitions"] == 3
    assert result["sent"] == 2
    assert result["deferred"] == 1
    # 실려 보낸 2건만 기준선이 이동한다.
    assert len(wired.upserts) == 2
    assert {r["code"] for r in wired.upserts} == set(codes[:2])
    # 꼬리는 카운터에 남아 다음 사이클에 이어서 발화한다.
    assert ("000002", "long") in alerts._pending
    assert "다음 사이클" in sent[0]


def test_renderers_do_not_slice_on_their_own():
    """자르는 주체는 호출부 하나여야 한다 — 렌더러가 또 자르면 같은 유실이 재발한다."""
    ts = [
        alerts.Transition(f"00000{i}", f"종목{i}", "long", dr.VIEW_HOLD, dr.VIEW_BUY, None, None)
        for i in range(5)
    ]
    text = alerts.render_slack_text(ts, NOW, total=5)

    assert text.count("•") == 5, "렌더러가 자체적으로 잘랐다"
    assert "다음 사이클" not in text


# ── Slack mrkdwn 주입 ──

def test_slack_escapes_mention_control_sequence():
    """종목명은 시트·외부 API 에서 오는 미검증 문자열이다.

    `<!channel>` 은 Slack 의 실제 멘션 제어 시퀀스다(python-slack-sdk 의 ChannelLink()
    가 `"<!channel|channel>"` 를 렌더한다) — 알림마다 채널 전원에게 푸시가 간다.
    """
    t = alerts.Transition(
        "005930", "삼성전자<!channel>", "long", dr.VIEW_HOLD, dr.VIEW_BUY, None, None
    )
    text = alerts.render_slack_text([t], NOW)

    assert "<!channel>" not in text
    assert "&lt;!channel&gt;" in text


def test_slack_escapes_ampersand():
    t = alerts.Transition("012450", "S&T모티브", "long", dr.VIEW_HOLD, dr.VIEW_BUY, None, None)
    text = alerts.render_slack_text([t], NOW)

    assert "S&amp;T모티브" in text


def test_slack_keeps_intended_markup():
    """이스케이프가 의도한 `*굵게*` 마크업 구조를 무너뜨리지 않아야 한다."""
    t = alerts.Transition("005930", "삼성전자", "long", dr.VIEW_HOLD, dr.VIEW_BUY, 71200.0, 1.83)
    text = alerts.render_slack_text([t], NOW)

    assert "*삼성전자*(005930)" in text
    assert "*매수*" in text


def test_escape_mrkdwn_order():
    """`&` 를 먼저 치환해야 한다 — 나중이면 `&lt;` 의 `&` 를 다시 이스케이프한다."""
    assert alert_channels.escape_mrkdwn("<a&b>") == "&lt;a&amp;b&gt;"
    assert alert_channels.escape_mrkdwn(None) == ""


# ── 숫자 포맷 방어 ──

@pytest.mark.parametrize("close,pct", [
    (float("nan"), 1.0), (float("inf"), 1.0), (71200.0, float("nan")), (None, None),
])
def test_non_finite_prices_do_not_leak_into_messages(close, pct):
    t = alerts.Transition("005930", "삼성전자", "long", dr.VIEW_HOLD, dr.VIEW_BUY, close, pct)
    text = alerts.render_slack_text([t], NOW)
    _, html_body = alerts.render_email([t], NOW)

    for out in (text, html_body):
        assert "nan" not in out.lower()
        assert "inf" not in out.lower()
