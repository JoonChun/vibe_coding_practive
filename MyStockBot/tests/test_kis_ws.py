"""KIS WebSocket — 무수신 워치독 + H0STCNT0 프레임 파서.

파서는 PRD §16.2 가 명시 요구한 테스트 대상(46필드 청킹)이었으나 그동안 비어 있었다.
워치독은 "소켓은 열려 있는데 틱이 없는" 좀비 연결을 감지하는 장치다.
"""
import asyncio

import pytest

from server.services import kis_ws

# ── H0STCNT0 파서 ──

def _record(
    code: str, price: str, sign: str, change: str, pct: str, volume: str,
    day_open: str = "", day_high: str = "", day_low: str = "",
) -> list[str]:
    """46필드 레코드 1건 생성(이 모듈이 쓰는 인덱스만 채우고 나머지는 빈 문자열).

    당일 시/고/저(7·8·9)는 기본 빈 문자열 — KIS 가 이 값을 비워 보내는 경우가 실제로
    있고, 그때도 틱 자체는 살아야 한다는 계약을 기본값으로 표현한다."""
    fields = [""] * kis_ws._CCNL_FIELD_COUNT
    fields[kis_ws._IDX_CODE] = code
    fields[kis_ws._IDX_TIME] = "093015"
    fields[kis_ws._IDX_PRICE] = price
    fields[kis_ws._IDX_SIGN] = sign
    fields[kis_ws._IDX_CHANGE] = change
    fields[kis_ws._IDX_CHANGE_PCT] = pct
    fields[kis_ws._IDX_VOLUME] = volume
    fields[kis_ws._IDX_DAY_OPEN] = day_open
    fields[kis_ws._IDX_DAY_HIGH] = day_high
    fields[kis_ws._IDX_DAY_LOW] = day_low
    return fields


def test_parse_single_record_rising():
    fields = _record("005930", "71000", "2", "1500", "2.16", "12345678")
    event = kis_ws._parse_ccnl_record(fields)

    assert event == {
        "type": "tick",
        "code": "005930",
        "price": 71000.0,
        "change": 1500.0,
        "change_pct": 2.16,
        "volume": 12345678,
        "time": "09:30:15",
        # 당일 시/고/저가 비어 오면 None — 틱은 살리고 진행중 1일봉만 못 만든다.
        "day_open": None,
        "day_high": None,
        "day_low": None,
    }


def test_parse_applies_sign_polarity_and_ignores_raw_sign():
    """부호는 PRDY_VRSS_SIGN 으로만 결정한다 — 원문에 '-' 가 있어도 이중 반전되지 않아야 함."""
    falling = kis_ws._parse_ccnl_record(_record("035720", "48000", "5", "-800", "-1.64", "1000"))
    assert falling["change"] == -800.0
    assert falling["change_pct"] == -1.64

    flat = kis_ws._parse_ccnl_record(_record("035720", "48000", "3", "0", "0", "1000"))
    assert flat["change"] == 0.0


def test_parse_rejects_short_record():
    assert kis_ws._parse_ccnl_record(["005930", "093015", "71000"]) is None


def test_parse_rejects_empty_code_and_bad_price():
    assert kis_ws._parse_ccnl_record(_record("", "71000", "2", "0", "0", "1")) is None
    assert kis_ws._parse_ccnl_record(_record("005930", "N/A", "2", "0", "0", "1")) is None


def test_handle_data_frame_chunks_multiple_records():
    """멀티 레코드 프레임(cnt>1)은 46필드 단위로 잘려 각각 tick 이벤트가 된다."""
    r1 = _record("005930", "71000", "2", "1500", "2.16", "100")
    r2 = _record("000660", "180000", "5", "2000", "-1.10", "200")
    raw = "0|H0STCNT0|002|" + "^".join(r1 + r2)

    events = kis_ws._handle_data_frame(raw)

    assert [e["code"] for e in events] == ["005930", "000660"]
    assert events[0]["change"] == 1500.0
    assert events[1]["change"] == -2000.0


def test_handle_data_frame_ignores_other_tr_id_and_encrypted():
    r1 = _record("005930", "71000", "2", "0", "0", "1")
    assert kis_ws._handle_data_frame("0|H0STASP0|001|" + "^".join(r1)) == []
    assert kis_ws._handle_data_frame("1|H0STCNT0|001|" + "^".join(r1)) == []
    assert kis_ws._handle_data_frame("0|H0STCNT0") == []  # 필드 부족


# ── 무수신 워치독 ──

class _FakeWs:
    """recv() 동작을 시나리오로 지정할 수 있는 가짜 연결."""

    def __init__(self, frames, hang_after=False):
        self._frames = list(frames)
        self._hang_after = hang_after
        self.sent: list[str] = []

    async def recv(self):
        if self._frames:
            return self._frames.pop(0)
        if self._hang_after:
            await asyncio.Event().wait()  # 영원히 대기 = TCP half-open 재현
        raise ConnectionError("closed")

    async def send(self, raw):
        self.sent.append(raw)


def test_read_loop_raises_idle_timeout_when_nothing_arrives(monkeypatch):
    """소켓은 열려 있는데 프레임이 끊긴 상태 → 워치독이 예외로 재연결을 유발해야 한다."""
    # 워치독 타임아웃을 짧게 줄여 테스트가 빠르게 끝나게 한다.
    monkeypatch.setattr(kis_ws, "_READ_IDLE_TIMEOUT_SECONDS", 0.05)
    ws = _FakeWs(frames=[], hang_after=True)

    with pytest.raises(kis_ws._ReadIdleTimeout):
        asyncio.run(kis_ws._read_loop(ws))


def test_read_loop_broadcasts_ticks_then_propagates_close(monkeypatch):
    monkeypatch.setattr(kis_ws, "_READ_IDLE_TIMEOUT_SECONDS", 5)
    raw = "0|H0STCNT0|001|" + "^".join(_record("005930", "71000", "2", "1500", "2.16", "100"))

    async def scenario():
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        kis_ws.add_listener(queue)
        try:
            # 프레임을 다 읽으면 연결 종료 예외가 올라가 호출부의 재연결 경로로 간다.
            with pytest.raises(ConnectionError):
                await kis_ws._read_loop(_FakeWs(frames=[raw]))
            return queue.get_nowait()
        finally:
            kis_ws.remove_listener(queue)

    event = asyncio.run(scenario())

    assert event["type"] == "tick"
    assert event["code"] == "005930"


def test_read_loop_echoes_pingpong(monkeypatch):
    """KIS 세션 유지는 받은 PINGPONG JSON 을 그대로 되돌려줘야 성립한다."""
    monkeypatch.setattr(kis_ws, "_READ_IDLE_TIMEOUT_SECONDS", 5)
    ping = '{"header":{"tr_id":"PINGPONG","datetime":"20260725093015"}}'
    ws = _FakeWs(frames=[ping])

    with pytest.raises(ConnectionError):
        asyncio.run(kis_ws._read_loop(ws))

    assert ws.sent == [ping]


def test_read_loop_survives_malformed_frame(monkeypatch):
    """프레임 1건의 파싱 이상이 연결 전체를 끊으면 안 된다(재구독 비용이 더 크다)."""
    monkeypatch.setattr(kis_ws, "_READ_IDLE_TIMEOUT_SECONDS", 5)
    good = "0|H0STCNT0|001|" + "^".join(_record("005930", "71000", "2", "0", "0", "1"))
    ws = _FakeWs(frames=["!!! not a frame", good])

    # 잘못된 프레임에서 멈추지 않고 계속 읽어, 끝에서야 연결 종료 예외가 난다.
    with pytest.raises(ConnectionError):
        asyncio.run(kis_ws._read_loop(ws))


# ────────────────────────────────────────────
# 당일 시/고/저 파싱 — 진행중 1일봉 합성의 입력
# ────────────────────────────────────────────

def test_parse_fills_day_ohl_when_present():
    fields = _record("005930", "71000", "2", "1500", "2.16", "12345678",
                     day_open="70000", day_high="71500", day_low="69800")
    event = kis_ws._parse_ccnl_record(fields)
    assert event["day_open"] == 70000.0
    assert event["day_high"] == 71500.0
    assert event["day_low"] == 69800.0


def test_parse_keeps_tick_alive_when_day_ohl_missing():
    """이 세 값이 비었다고 틱을 버리면 가격 표시까지 멈춘다 — 진행중 봉만 포기한다."""
    event = kis_ws._parse_ccnl_record(
        _record("005930", "71000", "2", "1500", "2.16", "12345678")
    )
    assert event is not None
    assert event["price"] == 71000.0
    assert event["day_open"] is None


def test_parse_tolerates_garbage_day_ohl():
    """숫자가 아닌 값이 와도 그 필드만 None 이고 나머지 틱은 정상이다."""
    event = kis_ws._parse_ccnl_record(
        _record("005930", "71000", "2", "1500", "2.16", "12345678",
                day_open="-", day_high="71500", day_low="")
    )
    assert event["day_open"] is None
    assert event["day_high"] == 71500.0
    assert event["day_low"] is None
