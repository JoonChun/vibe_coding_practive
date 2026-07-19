"""collector.py — 즉시 수집 트리거(_interruptible_wait/trigger_immediate_cycle)와
60분봉 초기 적재(_bootstrap_60m_if_needed) 유닛 테스트.

DB·네트워크는 전혀 열지 않는다 — db.get_candles_store/db.upsert_candles/
crawler.fetch_yf_ohlcv 를 전부 monkeypatch 로 대체해 순수하게 collector.py 자신의
분기 로직(신선도 게이트·쿨다운·예외 스왈로우)만 검증한다.

시간 의존성: _interruptible_wait 케이스는 threading.Event 폴링 자체가 최대 1초
단위라 실제 시간이 아주 조금(≤약 1초) 걸리는 게 정상 동작이다(구현 docstring
"1초 단위로 쪼개 기다리며" 참조) — 이를 실패로 오판하지 않도록 넉넉한 상한
(수 초)만 assert 한다. time.sleep/time.time 자체를 모킹하지 않는 이유: 이 함수는
내부적으로 Event.wait(1)만 쓰고 별도 시각 계산이 없어 모킹할 대상이 마땅치 않고,
실제 걸리는 시간이 짧아 모킹 없이도 결정적으로 빠르게 끝난다.
"""
import threading
import time

import pandas as pd
import pytest

import indicators
from server.services import collector


# ────────────────────────────────────────────
# 모듈 전역 상태 리셋(쿨다운 dict·이벤트) — tick_aggregator 테스트의 autouse 리셋
# 관례를 그대로 따른다.
# ────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_module_state():
    def _clear():
        collector._60m_bootstrap_cooldown.clear()
        collector._stop_event.clear()
        collector._trigger_event.clear()

    _clear()
    yield
    _clear()


# ────────────────────────────────────────────
# 1. _interruptible_wait / trigger_immediate_cycle
# ────────────────────────────────────────────

def test_interruptible_wait_returns_promptly_after_trigger_and_clears_event():
    collector.trigger_immediate_cycle()
    assert collector._trigger_event.is_set() is True

    start = time.monotonic()
    interrupted = collector._interruptible_wait(interval=30)
    elapsed = time.monotonic() - start

    assert interrupted is False  # 정상 만료가 아니라 trigger로 인한 즉시 재개
    assert elapsed < 3.0         # Event.wait(1) 폴링 한 틱 내(최대 약 1초) 반환
    assert collector._trigger_event.is_set() is False  # clear 되어야 다음 트리거와 안 섞임


def test_interruptible_wait_returns_immediately_on_stop_event():
    collector._stop_event.set()

    start = time.monotonic()
    interrupted = collector._interruptible_wait(interval=30)
    elapsed = time.monotonic() - start

    assert interrupted is True  # 루프 종료 신호
    assert elapsed < 3.0


def test_interruptible_wait_expires_normally_without_stop_or_trigger():
    """짧은 interval을 정상 만료시켜도(트리거·정지 없이) False를 반환해야 한다
    (기존 동작 보존 확인 — 너무 긴 interval로 테스트를 느리게 만들지 않는다)."""
    start = time.monotonic()
    interrupted = collector._interruptible_wait(interval=1)
    elapsed = time.monotonic() - start

    assert interrupted is False
    assert elapsed >= 1.0
    assert elapsed < 3.0


# ────────────────────────────────────────────
# 2. _bootstrap_60m_if_needed
# ────────────────────────────────────────────

_CODE = "005930"


def _fake_yf_60m_df(n: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02 09:00", periods=n, freq="60min", tz="Asia/Seoul")
    return pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [101.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [100.5 + i for i in range(n)],
        "volume": [1000 + i for i in range(n)],
    }, index=idx)


def test_bootstrap_60m_noop_when_store_already_has_enough_bars(monkeypatch):
    """저장소에 이미 MACD 최소 봉수 이상 있으면 외부 fetch를 아예 시도하지 않는다."""
    stored = [{"t": i, "close": 1.0} for i in range(indicators._MIN_BARS_MACD + 10)]
    monkeypatch.setattr(collector.db, "get_candles_store", lambda code, tf, limit: stored)

    fetch_calls = []
    monkeypatch.setattr(
        collector.crawler, "fetch_yf_ohlcv",
        lambda code, interval, period: fetch_calls.append(code) or _fake_yf_60m_df(),
    )
    upsert_calls = []
    monkeypatch.setattr(
        collector.db, "upsert_candles",
        lambda code, tf, items: upsert_calls.append((code, tf, items)),
    )

    collector._bootstrap_60m_if_needed(_CODE)

    assert fetch_calls == []
    assert upsert_calls == []


def test_bootstrap_60m_fetches_and_upserts_when_store_insufficient(monkeypatch):
    """저장소 봉수가 최소치 미만이면 yfinance 6개월치를 1회 조회해 upsert 한다."""
    monkeypatch.setattr(collector.db, "get_candles_store", lambda code, tf, limit: [])

    fetch_calls = []

    def _fake_fetch(code, interval, period):
        fetch_calls.append((code, interval, period))
        return _fake_yf_60m_df(n=5)

    monkeypatch.setattr(collector.crawler, "fetch_yf_ohlcv", _fake_fetch)

    upsert_calls = []
    monkeypatch.setattr(
        collector.db, "upsert_candles",
        lambda code, tf, items: upsert_calls.append((code, tf, items)),
    )

    collector._bootstrap_60m_if_needed(_CODE)

    assert fetch_calls == [(_CODE, "60m", "6mo")]
    assert len(upsert_calls) == 1
    code, tf, items = upsert_calls[0]
    assert code == _CODE
    assert tf == "60m"
    assert len(items) == 5
    assert items[0]["close"] == 100.5  # _df_to_candle_items_minute 변환 확인(close 보존)


def test_bootstrap_60m_does_not_refetch_within_cooldown(monkeypatch):
    """부족 상태가 그대로여도 쿨다운 창(SIXTY_MIN_BOOTSTRAP_RETRY_COOLDOWN_SECONDS)
    내 재호출이면 fetch를 다시 시도하지 않는다."""
    monkeypatch.setattr(collector.db, "get_candles_store", lambda code, tf, limit: [])

    fetch_calls = []
    monkeypatch.setattr(
        collector.crawler, "fetch_yf_ohlcv",
        lambda code, interval, period: fetch_calls.append(code) or _fake_yf_60m_df(),
    )
    monkeypatch.setattr(collector.db, "upsert_candles", lambda code, tf, items: None)

    collector._bootstrap_60m_if_needed(_CODE)
    collector._bootstrap_60m_if_needed(_CODE)  # 직후 재호출 — 쿨다운 창 안

    assert len(fetch_calls) == 1


def test_bootstrap_60m_swallows_fetch_exception_and_records_cooldown(monkeypatch):
    """fetch가 예외를 던져도 조용히 통과하고(예외 전파 없음) 쿨다운은 기록돼
    바로 다음 호출에서 재시도하지 않는다."""
    monkeypatch.setattr(collector.db, "get_candles_store", lambda code, tf, limit: [])

    fetch_calls = []

    def _raising_fetch(code, interval, period):
        fetch_calls.append(code)
        raise RuntimeError("yfinance 네트워크 실패(시뮬레이션)")

    monkeypatch.setattr(collector.crawler, "fetch_yf_ohlcv", _raising_fetch)

    upsert_calls = []
    monkeypatch.setattr(
        collector.db, "upsert_candles",
        lambda code, tf, items: upsert_calls.append((code, tf, items)),
    )

    collector._bootstrap_60m_if_needed(_CODE)  # 예외가 여기서 전파되면 테스트 실패
    assert len(fetch_calls) == 1
    assert upsert_calls == []

    collector._bootstrap_60m_if_needed(_CODE)  # 쿨다운 창 안 — 재시도 없어야 함
    assert len(fetch_calls) == 1
