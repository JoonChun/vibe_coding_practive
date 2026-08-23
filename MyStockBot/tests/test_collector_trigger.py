"""수집 루프 즉시 트리거 — 신규 관심종목이 다음 정기 사이클을 기다리지 않게.

## 왜 필요한가
수집 루프는 장중 30초·그 외 600초 간격으로 돈다. 관심종목을 새로 추가하면 다음
사이클까지 카드가 '—' 로 비어 있었고, 장외에는 그게 최대 10분이었다.

threading.Event 는 다중 대기를 지원하지 않으므로 정지와 즉시수집이 **한 이벤트**
(_wake_event)를 공유하고, 어느 쪽으로 깼는지는 _stop_event 로 구분한다. 그래서
여기서 잠글 것은 두 가지다 — 트리거가 실제로 대기를 끊는가, 그리고 정지 경로가
그대로 살아 있는가(트리거 도입이 종료를 망가뜨리지 않았는가).
"""
import threading
import time

import pytest

from server.services import collector


@pytest.fixture(autouse=True)
def _clean_events():
    """모듈 전역 이벤트를 테스트마다 초기화(다른 테스트의 잔여 상태 차단)."""
    collector._stop_event.clear()
    collector._wake_event.clear()
    yield
    collector._stop_event.set()
    collector._wake_event.set()


def test_trigger_sets_wake_event():
    assert not collector._wake_event.is_set()
    collector.trigger_immediate_cycle()
    assert collector._wake_event.is_set()


def test_trigger_interrupts_long_wait():
    """핵심 계약 — 600초 대기 중이어도 트리거가 즉시 깨운다."""
    woke_at: list[float] = []

    def waiter():
        collector._wake_event.wait(600)
        woke_at.append(time.monotonic())

    t = threading.Thread(target=waiter, daemon=True)
    started = time.monotonic()
    t.start()
    time.sleep(0.05)  # 스레드가 wait 에 진입할 여유
    collector.trigger_immediate_cycle()
    t.join(timeout=2)

    assert not t.is_alive(), "트리거가 대기를 끊지 못했다"
    assert woke_at and (woke_at[0] - started) < 1.0


def test_loop_runs_cycle_on_trigger_then_stops(monkeypatch):
    """트리거로 깬 사이클이 실제로 _run_cycle 을 부르고, 정지 요청은 사이클을 더
    돌리지 않고 즉시 빠져나온다."""
    calls: list[str] = []
    monkeypatch.setattr(collector, "_run_cycle", lambda: calls.append("cycle"))
    # 트리거가 없으면 절대 안 깨어나도록 대기 간격을 길게 둔다.
    monkeypatch.setattr(collector, "_cycle_interval_seconds", lambda: 600)

    t = threading.Thread(target=collector._loop, daemon=True)
    t.start()
    time.sleep(0.05)
    assert calls == ["cycle"], "부팅 직후 1회 사이클이 있어야 한다"

    collector.trigger_immediate_cycle()
    time.sleep(0.05)
    assert calls == ["cycle", "cycle"], "트리거로 한 사이클 더 돌아야 한다"

    collector.stop()
    t.join(timeout=2)
    assert not t.is_alive(), "정지 요청에 루프가 빠져나오지 못했다"
    assert calls == ["cycle", "cycle"], "정지 경로가 사이클을 추가로 돌리면 안 된다"


def test_stop_wakes_loop_without_waiting_full_interval(monkeypatch):
    """정지가 인터벌 전체를 기다리지 않는다 — 트리거 도입 전 동작(stop_event.wait)의 회귀."""
    monkeypatch.setattr(collector, "_run_cycle", lambda: None)
    monkeypatch.setattr(collector, "_cycle_interval_seconds", lambda: 600)

    t = threading.Thread(target=collector._loop, daemon=True)
    t.start()
    time.sleep(0.05)

    started = time.monotonic()
    collector.stop()
    t.join(timeout=2)

    assert not t.is_alive()
    assert (time.monotonic() - started) < 1.0


def test_trigger_during_cycle_is_consumed_on_next_wait(monkeypatch):
    """사이클 도중 들어온 트리거는 삼켜지지 않고 다음 대기에서 곧바로 소비된다 —
    그 사이클엔 새 종목이 안 잡혔을 수 있으므로 한 번 더 도는 것이 맞다."""
    calls: list[str] = []

    def slow_cycle():
        calls.append("cycle")
        if len(calls) == 1:
            collector.trigger_immediate_cycle()  # 사이클 실행 중 요청이 들어온 상황

    monkeypatch.setattr(collector, "_run_cycle", slow_cycle)
    monkeypatch.setattr(collector, "_cycle_interval_seconds", lambda: 600)

    t = threading.Thread(target=collector._loop, daemon=True)
    t.start()
    time.sleep(0.1)

    assert len(calls) == 2, "사이클 중 들어온 트리거가 다음 대기에서 소비되지 않았다"

    collector.stop()
    t.join(timeout=2)
