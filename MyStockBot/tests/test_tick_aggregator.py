"""tick_aggregator.py(틱 합성기) 유닛 테스트 — 이 레포 최초의 pytest 스위트.

오늘(KRX 휴장)은 실시간 틱으로 검증이 불가능하므로, 가짜 틱을 직접 주입해 월요일
개장 전 마지막 안전망 역할을 한다. 서버(uvicorn)는 절대 기동하지 않고, 모듈을 import한
뒤 내부 순수 함수(_ingest_tick 등)와 모듈 전역 인메모리 상태를 직접 검증한다 — 실 DB·
실 KIS 연결은 전혀 사용하지 않는다.

시간 주입 방식: _ingest_tick(event, now)는 이미 now를 인자로 받는 "순수 함수 성격"
(원본 docstring 참조)이라 monkeypatch 없이 원하는 시각을 직접 넣을 수 있다. 다만
_consume_loop()는 내부에서 time.time()을 직접 호출하므로(케이스 7), 그 경우에만
monkeypatch로 시각을 고정한다.
"""
import asyncio
import contextlib
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from config import TICK_AGG_RING_BUFFER_MAX_MINUTES
from server.services import tick_aggregator as tick_agg

_KST = ZoneInfo("Asia/Seoul")
_CODE = "005930"


def _epoch(y: int, m: int, d: int, hh: int, mm: int, ss: int = 0) -> float:
    return datetime(y, m, d, hh, mm, ss, tzinfo=_KST).timestamp()


def _tick(
    code: str = _CODE,
    price: float = 100.0,
    volume: int | None = None,
    day_open: float | None = None,
    day_high: float | None = None,
    day_low: float | None = None,
) -> dict:
    """kis_ws.py 가 발행하는 tick 이벤트 dict 계약(kis_ws.py 모듈 docstring)을 그대로 흉내낸다."""
    return {
        "type": "tick",
        "code": code,
        "price": price,
        "change": 0.0,
        "change_pct": 0.0,
        "volume": volume,
        "time": "09:00:00",
        "day_open": day_open,
        "day_high": day_high,
        "day_low": day_low,
    }


@pytest.fixture(autouse=True)
def _reset_module_state():
    """tick_aggregator 는 전부 모듈 전역 인메모리 상태 — 테스트 간 오염을 막기 위해
    매 테스트 전후로 초기화한다(실 서버라면 재시작에 해당하는 리셋)."""

    def _clear():
        tick_agg._day_bars.clear()
        tick_agg._minute_rings.clear()
        tick_agg._forming_minutes.clear()
        tick_agg._last_acml.clear()
        tick_agg._last_dates.clear()
        tick_agg._reference_state.clear()
        tick_agg._queue = None
        tick_agg._stop_event = None

    _clear()
    yield
    _clear()


# ────────────────────────────────────────────
# 1. 1분 버킷 롤오버
# ────────────────────────────────────────────

def test_minute_bucket_rollover_pushes_ring_and_starts_new_forming():
    t_1000 = _epoch(2024, 11, 19, 10, 0, 10)   # 10:00 분 버킷
    t_1000b = _epoch(2024, 11, 19, 10, 0, 45)  # 같은 분
    t_1001 = _epoch(2024, 11, 19, 10, 1, 5)    # 다음 분 버킷

    tick_agg._ingest_tick(_tick(price=100.0, volume=1000, day_open=100.0), t_1000)
    tick_agg._ingest_tick(_tick(price=105.0, volume=1050, day_open=100.0), t_1000b)

    # 같은 분 안에서는 형성중 봉만 갱신되고, 링버퍼는 아직 비어 있어야 한다.
    assert _CODE not in tick_agg._minute_rings
    forming = tick_agg._forming_minutes[_CODE]
    assert forming == {
        "t": int(t_1000) // 60 * 60,
        "open": 100.0, "high": 105.0, "low": 100.0, "close": 105.0, "volume": 50,
    }

    tick_agg._ingest_tick(_tick(price=98.0, volume=1100, day_open=100.0), t_1001)

    # 분 경계를 넘는 순간 직전 형성중 봉이 링버퍼로 밀리고, 새 형성중 봉이 시작돼야 한다.
    ring = list(tick_agg._minute_rings[_CODE])
    assert ring == [{
        "t": int(t_1000) // 60 * 60,
        "open": 100.0, "high": 105.0, "low": 100.0, "close": 105.0, "volume": 50,
    }]
    assert tick_agg._forming_minutes[_CODE] == {
        "t": int(t_1001) // 60 * 60,
        "open": 98.0, "high": 98.0, "low": 98.0, "close": 98.0, "volume": 50,
    }


# ────────────────────────────────────────────
# 2. 버킷 경계 재집계(1m 링버퍼 + 형성중 봉 → 5m/60m, resample_items 재사용 검증)
# ────────────────────────────────────────────

def test_progressing_5m_and_60m_reuse_resample_items_clock_aligned():
    # 케이스 1에서 이미 분 롤오버 자체(링버퍼 적재)는 검증했으므로, 여기서는
    # _derive_progressing_bucket 이 candles.resample_items() 를 실제로 재사용해
    # clock-aligned 버킷 규약대로 상위 tf 를 파생하는지만 겨냥한다 — 1분 링버퍼·형성중
    # 봉 상태를 직접 구성해 입력을 정확히 통제한다.
    t_1000 = int(_epoch(2024, 11, 19, 10, 0, 0))  # 정시 — 5m/60m 버킷 경계가 겹치는 지점
    ring_bars = [
        {"t": t_1000 + 0 * 60, "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10},
        {"t": t_1000 + 1 * 60, "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "volume": 12},
        {"t": t_1000 + 2 * 60, "open": 102.0, "high": 104.0, "low": 101.0, "close": 103.0, "volume": 8},
        {"t": t_1000 + 3 * 60, "open": 103.0, "high": 105.0, "low": 102.0, "close": 104.0, "volume": 15},
    ]
    forming = {
        "t": t_1000 + 4 * 60, "open": 104.0, "high": 106.0, "low": 103.0, "close": 105.0, "volume": 9,
    }

    tick_agg._minute_rings[_CODE] = deque(ring_bars, maxlen=TICK_AGG_RING_BUFFER_MAX_MINUTES)
    tick_agg._forming_minutes[_CODE] = forming

    expected = {
        "t": t_1000, "open": 100.0, "high": 106.0, "low": 99.0, "close": 105.0, "volume": 54,
    }

    assert tick_agg._progressing_bar(_CODE, "5m") == expected
    # 09:00 KST 정각 기준이라 이 5개 항목은 60m 버킷도 동일한 t 로 겹친다.
    assert tick_agg._progressing_bar(_CODE, "60m") == expected


# ────────────────────────────────────────────
# 3. 일봉 O(1) 조립
# ────────────────────────────────────────────

def test_day_bar_assembles_from_tick_fields_directly():
    t1 = _epoch(2024, 11, 19, 10, 0, 0)
    t2 = _epoch(2024, 11, 19, 10, 5, 0)
    t3 = _epoch(2024, 11, 19, 10, 10, 0)
    expected_t = int(datetime(2024, 11, 19, 0, 0, 0, tzinfo=_KST).timestamp())

    tick_agg._ingest_tick(
        _tick(price=100.0, volume=500, day_open=100.0, day_high=101.0, day_low=99.0), t1
    )
    assert tick_agg._day_bars[_CODE] == {
        "t": expected_t, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 500,
    }

    # 두 번째 틱 — day_open 파싱 실패(None) 상황을 흉내낸다: 이전 값이 그대로 carry.
    tick_agg._ingest_tick(
        _tick(price=103.0, volume=600, day_open=None, day_high=103.0, day_low=99.0), t2
    )
    assert tick_agg._day_bars[_CODE] == {
        "t": expected_t, "open": 100.0, "high": 103.0, "low": 99.0, "close": 103.0, "volume": 600,
    }

    # 세 번째 틱 — 저가 갱신.
    tick_agg._ingest_tick(
        _tick(price=98.0, volume=700, day_open=None, day_high=103.0, day_low=97.0), t3
    )
    assert tick_agg._day_bars[_CODE] == {
        "t": expected_t, "open": 100.0, "high": 103.0, "low": 97.0, "close": 98.0, "volume": 700,
    }


# ────────────────────────────────────────────
# 4. 거래량 차분(첫 틱 기준점 없음 / 음수 방지 가드)
# ────────────────────────────────────────────

def test_volume_delta_first_tick_zero_and_negative_guarded():
    t1 = _epoch(2024, 11, 19, 11, 0, 0)
    t2 = _epoch(2024, 11, 19, 11, 0, 10)  # 같은 분
    t3 = _epoch(2024, 11, 19, 11, 0, 20)  # 같은 분

    # 첫 틱 — 기준점이 없어 이번 틱의 기여분은 0.
    tick_agg._ingest_tick(_tick(price=100.0, volume=1000), t1)
    assert tick_agg._forming_minutes[_CODE]["volume"] == 0
    assert tick_agg._last_acml[_CODE] == 1000

    # 둘째 틱 — 누적거래량이 오히려 감소(비정상 데이터/재전송 등). 델타는 음수가 아니라 0.
    tick_agg._ingest_tick(_tick(price=99.0, volume=900), t2)
    assert tick_agg._forming_minutes[_CODE]["volume"] == 0  # 0 + max(900-1000, 0) = 0
    assert tick_agg._last_acml[_CODE] == 900  # 기준점 자체는 갱신됨(다음 델타 계산의 기준)

    # 셋째 틱 — 정상 증가. 이제부터 정상 차분.
    tick_agg._ingest_tick(_tick(price=101.0, volume=950), t3)
    assert tick_agg._forming_minutes[_CODE]["volume"] == 50  # 0 + max(950-900, 0) = 50
    assert tick_agg._last_acml[_CODE] == 950


# ────────────────────────────────────────────
# 5. 거래일 롤오버 리셋
# ────────────────────────────────────────────

def test_trading_day_rollover_resets_ring_daybar_and_volume_baseline():
    day1_t1 = _epoch(2024, 11, 19, 10, 0, 10)
    day1_t2 = _epoch(2024, 11, 19, 10, 1, 10)  # 분 롤오버 발생 → 링버퍼에 1건 적재
    day2_t1 = _epoch(2024, 11, 20, 9, 5, 0)    # 다음 거래일

    tick_agg._ingest_tick(
        _tick(price=100.0, volume=1000, day_open=100.0, day_high=101.0, day_low=99.0), day1_t1
    )
    tick_agg._ingest_tick(
        _tick(price=105.0, volume=1100, day_open=100.0, day_high=105.0, day_low=99.0), day1_t2
    )

    assert _CODE in tick_agg._minute_rings and len(tick_agg._minute_rings[_CODE]) == 1
    assert tick_agg._last_acml[_CODE] == 1100
    assert tick_agg._last_dates[_CODE] == "20241119"

    tick_agg._ingest_tick(
        _tick(price=98.0, volume=200, day_open=98.0, day_high=99.0, day_low=97.0), day2_t1
    )

    # 날짜가 바뀌었으므로 링버퍼·형성중봉·차분 기준점이 전부 리셋되고, 이번 틱만으로
    # 완전히 새로 조립돼야 한다(전날 값이 하나도 섞이면 안 된다).
    assert tick_agg._last_dates[_CODE] == "20241120"
    assert _CODE not in tick_agg._minute_rings  # 리셋 직후엔 아직 분 롤오버가 없어 재생성 안 됨

    expected_day2_t = int(datetime(2024, 11, 20, 0, 0, 0, tzinfo=_KST).timestamp())
    assert tick_agg._day_bars[_CODE] == {
        "t": expected_day2_t, "open": 98.0, "high": 99.0, "low": 97.0, "close": 98.0, "volume": 200,
    }
    assert tick_agg._last_acml[_CODE] == 200  # 전날 1100은 완전히 잊혀지고 200부터 새 기준점
    forming = tick_agg._forming_minutes[_CODE]
    assert forming["open"] == 98.0
    assert forming["volume"] == 0  # 새 기준점 — 델타 0부터 재시작(전날 값과 차분되지 않음)


# ────────────────────────────────────────────
# 6. 참고 판정 dedup 규칙(_merge_progressing 직접 호출)
# ────────────────────────────────────────────
# _merge_progressing 은 이미 리스트로 넘어온 확정 이력과 진행중 봉을 병합만 하는 순수
# 함수라(내부에서 db 를 호출하지 않는다) 이 함수 자체를 직접 호출해 검증한다. 계획서의
# "DB monkeypatch" 는 상위 호출부(_recompute_reference_for_code, db.get_candles_store를
# 실제로 호출)를 테스트할 경우를 대비한 안전장치였는데, 지시대로 병합 함수를 직접
# 호출하는 편이 더 결정적이고 단순해 이 경로를 택했다 — DB는 전혀 건드리지 않는다.

def test_merge_progressing_none_returns_history_as_is():
    history = [{"t": 100, "close": 1.0}]
    assert tick_agg._merge_progressing(history, None) is history


def test_merge_progressing_appends_when_t_differs():
    history = [{"t": 100, "close": 1.0}]
    progressing = {"t": 200, "close": 2.0}
    assert tick_agg._merge_progressing(history, progressing) == [
        {"t": 100, "close": 1.0}, {"t": 200, "close": 2.0},
    ]


def test_merge_progressing_replaces_last_when_t_matches():
    history = [{"t": 100, "close": 1.0}, {"t": 200, "close": 2.0}]
    progressing = {"t": 200, "close": 2.5}
    assert tick_agg._merge_progressing(history, progressing) == [
        {"t": 100, "close": 1.0}, {"t": 200, "close": 2.5},
    ]


def test_merge_progressing_empty_history_with_progressing():
    assert tick_agg._merge_progressing([], {"t": 100, "close": 1.0}) == [{"t": 100, "close": 1.0}]


# ────────────────────────────────────────────
# 7. 비-tick 이벤트 무시(_consume_loop 필터링)
# ────────────────────────────────────────────

def test_consume_loop_ignores_non_tick_events(monkeypatch):
    """이 저장소는 pytest-asyncio 를 쓰지 않는다 — async 시나리오는 asyncio.run() 으로
    감싼다(tests/test_kis_ws.py 와 동일 관례). 의존성 하나를 아끼려는 선택이다."""
    asyncio.run(_consume_loop_scenario(monkeypatch))


async def _consume_loop_scenario(monkeypatch):
    fixed_now = _epoch(2024, 11, 19, 10, 0, 0)
    monkeypatch.setattr(tick_agg.time, "time", lambda: fixed_now)

    tick_agg._queue = asyncio.Queue()
    tick_agg._stop_event = asyncio.Event()  # _consume_loop 진입 assert 용(실제로 set()은 안 함)

    # tick_aggregator 자신이 내보낸 bar_update, kis_ws 의 status 가 같은 큐로 되돌아오는
    # 상황을 그대로 흉내낸다 — 이 둘은 무시되고 tick 만 반영돼야 한다.
    await tick_agg._queue.put({"type": "status", "kis_connected": True, "subscribed": []})
    await tick_agg._queue.put(
        {"type": "bar_update", "code": _CODE, "tf": "1m", "bar": {}, "live": True}
    )
    await tick_agg._queue.put(_tick(price=100.0, volume=1000, day_open=100.0))

    consume_task = asyncio.create_task(tick_agg._consume_loop())
    try:
        for _ in range(50):
            if _CODE in tick_agg._day_bars:
                break
            await asyncio.sleep(0.01)
    finally:
        consume_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consume_task

    # status/bar_update 는 무시되고, tick 1건만 진행중 봉에 반영돼야 한다.
    assert _CODE in tick_agg._day_bars
    assert tick_agg._day_bars[_CODE]["close"] == 100.0
    assert tick_agg._forming_minutes[_CODE]["volume"] == 0  # 첫 틱이라 델타 0(케이스 4와 동일 규칙)


# ────────────────────────────────────────────
# 8. _bar_has_all_fields — 전 필드 검증(결함4). volume=0은 falsy이지만 "유효한 값"
# (거래 없음 등)이므로 None과 반드시 구분돼야 한다 — 0을 None으로 오판하면 실버그.
# ────────────────────────────────────────────

def _full_bar(**overrides) -> dict:
    bar = {"t": 100, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10}
    bar.update(overrides)
    return bar


def test_bar_has_all_fields_true_when_all_numeric_including_zero_volume():
    assert tick_agg._bar_has_all_fields(_full_bar()) is True
    # volume=0(거래 없음 등)은 값이 "있는" 상태 — None과 절대 혼동되면 안 된다.
    assert tick_agg._bar_has_all_fields(_full_bar(volume=0)) is True


@pytest.mark.parametrize("missing_field", ["open", "high", "low", "close", "volume"])
def test_bar_has_all_fields_false_when_any_single_field_is_none(missing_field):
    bar = _full_bar(**{missing_field: None})
    assert tick_agg._bar_has_all_fields(bar) is False


# ────────────────────────────────────────────
# 9. _snapshot_code — day_bar/ring/forming 스냅샷 뜨기(빈 상태 안전 + forming 불변식)
# ────────────────────────────────────────────

def test_snapshot_code_returns_safe_defaults_for_unknown_code():
    assert tick_agg._snapshot_code("999999") == {"day_bar": None, "ring": [], "forming": None}


def test_snapshot_code_copies_forming_so_in_place_mutation_does_not_leak():
    tick_agg._day_bars[_CODE] = _full_bar(t=1)
    tick_agg._forming_minutes[_CODE] = {
        "t": 2, "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 5,
    }
    tick_agg._minute_rings[_CODE] = deque(
        [{"t": 0, "open": 9.0, "high": 9.0, "low": 9.0, "close": 9.0, "volume": 1}],
        maxlen=TICK_AGG_RING_BUFFER_MAX_MINUTES,
    )

    snapshot = tick_agg._snapshot_code(_CODE)
    assert isinstance(snapshot["ring"], list)  # deque가 아니라 list로 복사돼야 함

    # _ingest_tick 이 forming 을 in-place 로 계속 변형하는 실제 패턴을 그대로 재현한다
    # (스냅샷 함수 docstring의 "forming은 반드시 dict()로 얕은 복사" 불변식 검증).
    tick_agg._forming_minutes[_CODE]["close"] = 999.0
    tick_agg._forming_minutes[_CODE]["volume"] = 12345

    assert snapshot["forming"] == {
        "t": 2, "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 5,
    }


# ────────────────────────────────────────────
# 10. _compute_progressing_bars — 전 종목·전 tf 일괄 계산(결함1·4)
# ────────────────────────────────────────────

def test_compute_progressing_bars_empty_snapshots_returns_empty():
    assert tick_agg._compute_progressing_bars({}) == []


def test_compute_progressing_bars_skips_incomplete_day_bar_when_no_minute_data():
    snapshot = {
        "day_bar": {"t": 1, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": None},
        "ring": [],
        "forming": None,
    }
    # 1일봉은 필드 미완성이라 스킵되고, 분봉 계열은 재료(ring/forming)가 아예 없어 None →
    # 결과적으로 이 종목은 어떤 tf 도 브로드캐스트 대상에 오르지 않는다.
    assert tick_agg._compute_progressing_bars({_CODE: snapshot}) == []


def test_compute_progressing_bars_includes_zero_volume_bar_and_excludes_incomplete_day_bar():
    # 검증 대상: volume=0 인 forming 도 "필드 완결"로 인정돼 살아남는가(0 은 falsy 라
    # 순진하게 짜면 미완성으로 오판된다).
    #
    # forming 하나뿐(t=120초)이라 5m 이상 버킷은 전부 시작점(t=0)이 비어 있는 축소
    # 버킷이 되어 가드에 걸린다 — 1분봉만 남는 것이 정상이다(버킷이 곧 그 분 자체).
    forming = {"t": 120, "open": 5.0, "high": 5.0, "low": 5.0, "close": 5.0, "volume": 0}
    snapshot = {"day_bar": None, "ring": [], "forming": forming}

    bars = tick_agg._compute_progressing_bars({_CODE: snapshot})
    tfs = {tf for (_, tf, _) in bars}

    assert "1d" not in tfs   # day_bar 가 None
    assert tfs == {"1m"}
    one_minute_bar = next(bar for (_, tf, bar) in bars if tf == "1m")
    assert one_minute_bar == forming
    assert one_minute_bar["volume"] == 0  # falsy 지만 필드 완결 판정에서 살아남아야 함


def test_compute_progressing_bars_multi_code_and_multi_tf():
    t_1000 = int(_epoch(2024, 11, 19, 10, 0, 0))
    ring_bars = [
        {"t": t_1000 + i * 60, "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i,
         "close": 100.5 + i, "volume": 10}
        for i in range(4)
    ]
    forming = {"t": t_1000 + 4 * 60, "open": 104.0, "high": 106.0, "low": 103.0,
               "close": 105.0, "volume": 9}
    day_bar = {"t": 0, "open": 90.0, "high": 110.0, "low": 85.0, "close": 105.0, "volume": 999}

    code_a, code_b = "005930", "000660"
    snapshots = {
        code_a: {"day_bar": day_bar, "ring": ring_bars, "forming": forming},
        code_b: {"day_bar": None, "ring": [], "forming": None},  # 재료 전무 — 전부 스킵돼야 함
    }

    bars = tick_agg._compute_progressing_bars(snapshots)
    codes_seen = {code for (code, _, _) in bars}
    assert codes_seen == {code_a}  # code_b 는 빈 스냅샷 안전 처리로 아예 결과에서 빠져야 한다

    tfs_seen = {tf for (code, tf, _) in bars if code == code_a}
    # 위와 같은 이유로 120m/240m 은 축소 버킷이라 제외된다.
    assert tfs_seen == set(tick_agg._ALL_TFS) - {"120m", "240m"}

    day_result = next(bar for (code, tf, bar) in bars if code == code_a and tf == "1d")
    assert day_result == day_bar  # 1d는 day_bar 그대로(재집계 없음)

    five_min = next(bar for (code, tf, bar) in bars if code == code_a and tf == "5m")
    assert five_min["open"] == 100.0     # 첫 항목(ring[0])의 open
    assert five_min["high"] == 106.0     # forming의 high가 최댓값
    assert five_min["low"] == 99.0       # ring[0]의 low가 최솟값
    assert five_min["close"] == 105.0    # 마지막 항목(forming)의 close
    assert five_min["volume"] == 49      # ring 4건(10×4) + forming(9) 합산


# ────────────────────────────────────────────
# 11. _active_codes — 당일 게이트 + kis_ws.get_status() 교집합(결함3)
# ────────────────────────────────────────────

def test_active_codes_day_gate_excludes_stale_codes_when_subscribed_empty(monkeypatch):
    today = "20241119"
    tick_agg._last_dates["005930"] = today       # 오늘 틱 있음 — 대상
    tick_agg._last_dates["000660"] = "20241118"  # 전일 stale(새 틱 아직 없음) — 제외돼야 함

    monkeypatch.setattr(
        tick_agg.kis_ws, "get_status",
        lambda: {"kis_connected": True, "subscribed": []},
    )

    # subscribed 가 비어 있으면(부팅 초기 등) 교집합은 건너뛰지만, 당일 게이트 자체는
    # 여전히 적용돼야 한다(결함3의 핵심 — 무력화되면 안 됨).
    assert tick_agg._active_codes(today) == {"005930"}


def test_active_codes_intersects_with_subscribed_when_non_empty(monkeypatch):
    today = "20241119"
    tick_agg._last_dates["005930"] = today
    tick_agg._last_dates["000660"] = today
    tick_agg._last_dates["035420"] = today

    monkeypatch.setattr(
        tick_agg.kis_ws, "get_status",
        lambda: {"kis_connected": True, "subscribed": ["005930", "999999"]},
    )

    # 당일 종목 {005930,000660,035420} ∩ 구독 종목 {005930,999999} = {005930} 만 남아야 한다.
    assert tick_agg._active_codes(today) == {"005930"}


# ────────────────────────────────────────────
# 12. _reference_worker — None 진행중 봉을 스킵해도 확정 이력만으로 판정이 "진행"되는지
# (판정 자체가 통째로 건너뛰어지면 안 된다 — 결함4의 후속 계약)
# ────────────────────────────────────────────

def _synthetic_history(n: int, start_price: float = 100.0) -> list[dict]:
    """MACD(26+9=35)·RSI(14) 최소 표본 수를 넉넉히 넘기는 합성 확정 이력. indicators.py는
    실물(ta 라이브러리)을 그대로 태워 "데이터부족"이 아닌 실신호가 나오는지만 검증하고,
    ta 내부 구현에 결합되지 않도록 정확한 신호 문자열까지는 하드코딩하지 않는다."""
    items = []
    price = start_price
    for i in range(n):
        price += 1.0 if i % 3 else -0.5  # 단조 증가가 아니라 등락을 섞어 실데이터에 가깝게
        items.append({
            "t": i * 60, "open": price, "high": price + 1, "low": price - 1,
            "close": price, "volume": 100 + i,
        })
    return items


def test_reference_worker_proceeds_with_history_only_when_progressing_bars_incomplete(monkeypatch):
    daily_hist = _synthetic_history(40)
    hour_hist = _synthetic_history(40, start_price=200.0)

    monkeypatch.setattr(
        tick_agg.db, "get_candles_store",
        lambda code, tf, limit: daily_hist if tf == "1d" else hour_hist,
    )

    # day_bar/forming 모두 필드가 하나씩 빠진 "미완성" 진행중 봉 — _reference_worker 가
    # 이들을 None 처리하고(결함4) 확정 이력만으로 병합해야 한다.
    snapshot = {
        "day_bar": {"t": 999, "open": None, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 500},
        "ring": [],
        "forming": {"t": 1000, "open": 105.0, "high": 106.0, "low": 104.0, "close": 105.5, "volume": None},
    }

    judgment = tick_agg._reference_worker(_CODE, snapshot, per=8.0, pbr=0.9, roe=18.0)

    # 판정이 통째로 건너뛰어지지 않고("데이터부족"/None 이 아니라) 확정 이력 40건만으로
    # 실제 신호가 나와야 한다 — 진행중 봉이 비정상이어도 참고 판정 자체는 죽지 않는다는 계약.
    assert judgment["short_view_live"] != "데이터부족"
    assert judgment["short_score_live"] is not None
    assert judgment["long_view_live"] != "데이터부족"
    assert judgment["long_score_live"] is not None


# ────────────────────────────────────────────
# 축소 버킷 가드 — 장중 재시작 회귀
# ────────────────────────────────────────────

def test_shrunken_bucket_is_skipped_after_restart():
    """장중에 서버를 재시작하면 링버퍼가 비어, 그 뒤 몇 분치만 담긴 '60분봉'이 만들어진다.
    그걸 내보내면 차트에서 이력의 올바른 부분봉을 **더 작은 값으로 덮어쓴다** —
    고가·저가·거래량이 전부 축소되므로 지표까지 오염된다. 내보내지 않는 것이 맞다."""
    # 10:47 부터의 3분치만 보유 → 60m 버킷(10:00 시작)의 앞 47분이 없다
    t = int(_epoch(2024, 11, 19, 10, 47, 0))
    ring = [
        {"t": t + i * 60, "open": 100.0, "high": 101.0, "low": 99.0,
         "close": 100.0, "volume": 5}
        for i in range(3)
    ]
    assert tick_agg._derive_progressing_bucket_from_items(ring, None, 60) is None


def test_full_bucket_is_emitted():
    """가드가 과잉 차단하지 않는다 — 버킷 시작부터 데이터가 있으면 정상 송출된다."""
    t = int(_epoch(2024, 11, 19, 10, 0, 0))  # 60m 버킷 시작과 일치
    ring = [
        {"t": t + i * 60, "open": 100.0, "high": 101.0 + i, "low": 99.0,
         "close": 100.0, "volume": 5}
        for i in range(3)
    ]
    bucket = tick_agg._derive_progressing_bucket_from_items(ring, None, 60)
    assert bucket is not None
    assert bucket["t"] == t
    assert bucket["high"] == 103.0
    assert bucket["volume"] == 15


def test_one_minute_bucket_never_shrinks():
    """1분봉은 버킷이 곧 그 분 자체라 축소 개념이 없다 — 가드가 걸리면 안 된다."""
    t = int(_epoch(2024, 11, 19, 10, 47, 0))
    forming = {"t": t, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 3}
    assert tick_agg._derive_progressing_bucket_from_items(None, forming, 1) == forming


def test_judgment_carries_warming_axis():
    """확정 판정과 같은 워밍업 축(60분봉 개수)을 실시간에도 실어야 한다 — 없으면
    확정 칩은 '축적 중'인데 LIVE 칩은 '관망'이 뜨는 모순이 생긴다."""
    hour_items = [
        {"t": i * 3600, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1}
        for i in range(12)
    ]
    result = tick_agg._compute_judgment([], hour_items, None, None, None)
    assert result["bars_60m_live"] == 12
