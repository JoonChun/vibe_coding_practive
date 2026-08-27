"""틱 합성기 — kis_ws 가 소비한 틱을 받아 진행중(미확정) 봉을 인메모리로 합성하고,
브라우저에는 2초 주기 bar_update 브로드캐스트를, 판정 화면에는 5초 주기 실시간
참고 판정(참고용, 확정 아님)을 제공한다.

collector.py(외부 API 폴링·확정 봉 DB 영속화)와 책임을 분리한다 — 이 모듈은 순수
인메모리 상태만 가지며 DB에 쓰지 않는다(서버 재시작 시 진행중 봉 유실은 허용:
어차피 다음 틱부터 다시 합성되고, 확정 이력은 collector/candles.py 가 이미 DB에
영속화해 두었으므로 참고 판정도 몇 초 안에 원래 흐름을 되찾는다).

공개 인터페이스:
    - start() / stop(): FastAPI lifespan 에서 kis_ws.start() *이후*에 각 1회 호출해야
      한다(자체 asyncio.Queue 로 kis_ws.add_listener 등록에 의존하므로 순서가 중요).
    - get_reference_state() -> dict[code, {...}]: 종목별 최신 실시간 참고 판정 스냅샷
      (얕은 복사본). 값 스키마:
        {"short_view_live": str|None, "short_score_live": int|None,
         "long_view_live": str|None, "long_score_live": int|None,
         "updated_at": "ISO8601 문자열"}
      계산 불가한 항목은 None. 장외에는 마지막 값을 그대로 freeze(삭제하지 않음).

발행 이벤트(kis_ws.broadcast_event() 로 위임해 큐로 push):
    {"type": "bar_update", "code": str,
     "tf": "1m"|"5m"|"15m"|"30m"|"60m"|"120m"|"240m"|"1d",
     "bar": {"t": int, "open": float, "high": float,
             "low": float, "close": float, "volume": int},
     "live": True}
    (2초 주기, 장중에만, 당일 틱을 받은 적 있는 종목만 대상. open/high/low/close/volume
     중 하나라도 아직 None 인 진행중 봉은 이 계약을 만족하지 못하므로 아예 보내지
     않는다 — "필드가 다 차기 전엔 안 보낸다"가 계약이지, null 필드를 실어 보내는 게
     계약이 아니다. 브라우저 parseLiveBar 도 전 필드 숫자를 전제한다.)

동작 개요:
    1) 소비 태스크(_consume_loop): kis_ws 에 자체 큐로 등록해 push 받는 이벤트 중
       type == "tick" 인 것만 골라 _ingest_tick 으로 진행중 봉에 반영한다(자기 자신이
       내보낸 bar_update, kis_ws 의 status 등은 무시 — 같은 큐로 되돌아오므로 반드시
       걸러야 한다).
    2) 봉 브로드캐스트 태스크(_bar_broadcast_loop, TICK_AGG_BAR_BROADCAST_INTERVAL_SECONDS):
       장중에만(collector._is_market_hours 와 동일 관례로 이 모듈에 로컬 구현), 당일
       틱을 받은 적 있는 종목(_active_codes) × 전 tf 의 진행중 봉을 bar_update 로
       내보낸다. 3단 구조로 이벤트루프 블로킹·큐 범람을 막는다: ①루프 스레드에서 종목별
       day_bar/ring/forming 스냅샷을 뜨고(저렴한 dict 복사만), ②asyncio.to_thread 1회로
       전 종목·전 tf 의 진행중 봉을 일괄 계산(_compute_progressing_bars — candles
       .resample_items() 재사용, pandas 연산이 여기 전부 몰림), ③송출 루프에서
       kis_ws.broadcast_event() 로 하나씩 내보내되 약 20건마다 asyncio.sleep(0) 을 끼워
       WS 송신 태스크가 리스너 큐를 드레인할 기회를 준다(41종목×8tf=최대 328건을 yield
       없이 쏟아내면 클라이언트 큐가 넘쳐 앞쪽 종목들이 drop-oldest 로 유실됐던 문제).
    3) 참고 판정 태스크(_reference_loop, TICK_AGG_REFERENCE_INTERVAL_SECONDS): 장중에만,
       당일 틱을 받은 적 있는 종목(_active_codes)만 대상으로, 확정 이력
       (db.get_candles_store)뒤에 진행중 봉을 이어붙여 indicators.py 순수 함수로
       단기(60분봉)·장기(1일봉+재무) view/score 를 재계산한다. 재무(per/pbr/roe)는
       collector 가 이미 캐시해둔 값을 재사용한다(중복 조회 없음, 이벤트루프에 남겨도
       무해 — 인메모리 조회). 동기 SQLite I/O(db.get_candles_store ×2)와 pandas/지표
       연산은 전부 단일 asyncio.to_thread(_reference_worker) 안에서 수행해 이벤트루프
       (uvicorn 워커=1)를 블로킹하지 않는다 — KIS PINGPONG 에코 지연 방지.

두 루프 모두 "당일(_last_dates[code] == 오늘 KST) 게이트"를 대상 선정에 적용한다 —
관심종목에서 빠진 종목·전일 stale 봉이 세션 내내(또는 다음 거래일 첫 틱 전까지)
브로드캐스트/판정 대상으로 남는 것을 막는다.

장 외 시간·틱 없음은 정상 상태다. 종목별 예외는 격리해 경고 로그만 남기고 다음
주기에 재시도한다 — 한 종목 실패가 전체 루프를 죽이지 않는다.
"""
import asyncio
import contextlib
import logging
import time
from collections import deque
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

import db
import indicators
from config import (
    TICK_AGG_BAR_BROADCAST_INTERVAL_SECONDS,
    TICK_AGG_REFERENCE_INTERVAL_SECONDS,
    TICK_AGG_RING_BUFFER_MAX_MINUTES,
    TIMEZONE,
)

import decision_rules as rules

from . import candles, collector, kis_ws

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# 상수
# ────────────────────────────────────────────

# tf → 1분 캔들 몇 개를 묶는지(1m/1d 는 별도 취급 — 아래 _progressing_bar 참고).
_UNIT_MINUTES = {"5m": 5, "15m": 15, "30m": 30, "60m": 60, "120m": 120, "240m": 240}
_ALL_TFS = ("1m", "5m", "15m", "30m", "60m", "120m", "240m", "1d")

# collector._is_market_hours 와 동일 관례(장중 09:00~15:40 Asia/Seoul, 평일).
_MARKET_OPEN = dtime(9, 0)
_MARKET_CLOSE = dtime(15, 40)


# ────────────────────────────────────────────
# 모듈 상태 — 전부 인메모리, DB 영속화 없음(서버 재시작 시 유실 허용)
# ────────────────────────────────────────────

_queue: asyncio.Queue | None = None
_tasks: list[asyncio.Task] = []
_stop_event: asyncio.Event | None = None

# 종목별 진행중 1일봉 — {"t","open","high","low","close","volume"}
_day_bars: dict[str, dict] = {}
# 종목별 당일 1분 확정봉 링버퍼(최근 TICK_AGG_RING_BUFFER_MAX_MINUTES건, t 오름차순)
_minute_rings: dict[str, deque] = {}
# 종목별 형성중 1분봉 — {"t","open","high","low","close","volume"}
_forming_minutes: dict[str, dict] = {}
# 종목별 마지막으로 관측한 누적거래량(ACML) — 분봉 volume 차분 기준점
_last_acml: dict[str, int] = {}
# 종목별 마지막 관측 거래일(KST, "YYYYMMDD") — 날짜가 바뀌면 롤오버
_last_dates: dict[str, str] = {}
# 종목별 최신 실시간 참고 판정(원자 교체 — 값 전체를 새 dict 로 바꿔치기)
_reference_state: dict[str, dict] = {}


# ────────────────────────────────────────────
# 공개 인터페이스
# ────────────────────────────────────────────

async def start() -> None:
    """자체 큐로 kis_ws.add_listener 등록 + 소비 태스크·주기 태스크 2개 기동.

    kis_ws.start() 이후에 호출해야 한다(리스너 등록만으로 충분하지만, 순서가 뒤바뀌어도
    치명적이지는 않다 — add_listener 는 kis_ws 연결 여부와 무관하게 항상 성공한다).
    """
    global _queue, _stop_event
    _stop_event = asyncio.Event()
    _queue = asyncio.Queue()  # 무제한 — 내부 전용 큐라 틱 유실보다 메모리 여유를 우선
    kis_ws.add_listener(_queue)
    _tasks.append(asyncio.create_task(_consume_loop(), name="tick-aggregator-consume"))
    _tasks.append(
        asyncio.create_task(_bar_broadcast_loop(), name="tick-aggregator-bar-broadcast")
    )
    _tasks.append(asyncio.create_task(_reference_loop(), name="tick-aggregator-reference"))
    logger.info("[tick_aggregator] 시작")


async def stop() -> None:
    """모든 내부 태스크를 정리하고 kis_ws 리스너 등록을 해제한다."""
    if _stop_event is not None:
        _stop_event.set()

    for task in list(_tasks):
        await _cancel_task(task)
    _tasks.clear()

    if _queue is not None:
        kis_ws.remove_listener(_queue)

    logger.info("[tick_aggregator] 정지")


def get_reference_state() -> dict[str, dict]:
    """종목별 최신 실시간 참고 판정 스냅샷(얕은 복사본 — 외부에서 내부 dict 를 직접
    변형하지 못하도록)."""
    return dict(_reference_state)


# ────────────────────────────────────────────
# 태스크 정리 유틸(kis_ws.py 와 동일 패턴)
# ────────────────────────────────────────────

async def _cancel_task(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning("[tick_aggregator] 태스크 정리 중 예외(무시하고 계속): %s", e)


async def _interruptible_sleep(seconds: float) -> None:
    """seconds 만큼 대기하되, stop() 이 호출되면 즉시 깨어난다."""
    if _stop_event is None:
        await asyncio.sleep(seconds)
        return
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(_stop_event.wait(), timeout=seconds)


# ────────────────────────────────────────────
# KST 시간 유틸
# ────────────────────────────────────────────

def _kst_now(now: float) -> datetime:
    return datetime.fromtimestamp(now, tz=ZoneInfo(TIMEZONE))


def _kst_date_str(now: float) -> str:
    return _kst_now(now).strftime("%Y%m%d")


def _kst_midnight_epoch(now: float) -> int:
    midnight = _kst_now(now).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())


def _is_market_hours(now: datetime) -> bool:
    return now.weekday() < 5 and _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


# ────────────────────────────────────────────
# 틱 ingest(순수 함수 성격 — 테스트 주입 가능하도록 now 를 인자로 받는다)
# ────────────────────────────────────────────

def _reset_code_state(code: str) -> None:
    """새 거래일 롤오버 — 링버퍼·형성중 봉·거래량 차분 기준점을 리셋한다.
    (_reference_state 는 건드리지 않는다 — 장 재개 후 참고 판정 태스크가 자연히 갱신)."""
    _day_bars.pop(code, None)
    _minute_rings.pop(code, None)
    _forming_minutes.pop(code, None)
    _last_acml.pop(code, None)


def _ingest_tick(event: dict, now: float) -> None:
    """kis_ws 의 tick 이벤트 1건을 진행중 봉에 반영한다. code/price 없으면 무시."""
    code = event.get("code")
    price = event.get("price")
    if not code or price is None:
        return

    volume = event.get("volume")  # 누적거래량(ACML). 파싱 실패 시 None 가능.
    day_open = event.get("day_open")
    day_high = event.get("day_high")
    day_low = event.get("day_low")

    today = _kst_date_str(now)
    if _last_dates.get(code) not in (None, today):
        _reset_code_state(code)  # 거래일이 바뀜 — 링버퍼·일봉·차분 기준점 리셋
    _last_dates[code] = today

    # ── 진행중 1일봉(O(1) 조립 — 별도 합성 불필요, 틱이 이미 당일 시가/고가/저가를 준다) ──
    prev_day_bar = _day_bars.get(code)
    _day_bars[code] = {
        "t": _kst_midnight_epoch(now),
        "open": day_open if day_open is not None else (prev_day_bar or {}).get("open"),
        "high": day_high if day_high is not None else (prev_day_bar or {}).get("high"),
        "low": day_low if day_low is not None else (prev_day_bar or {}).get("low"),
        "close": price,
        "volume": volume if volume is not None else (prev_day_bar or {}).get("volume"),
    }

    # ── 거래량 차분(분봉 volume 용). 첫 틱/롤오버 직후엔 차분 기준점이 없어 이번 틱의
    #    기여분은 0으로 둔다(그 다음 틱부터 정상 차분). 음수는 0으로 가드.
    vol_delta = 0
    if volume is not None:
        baseline = _last_acml.get(code)
        if baseline is not None:
            vol_delta = max(volume - baseline, 0)
        _last_acml[code] = volume

    # ── 당일 1분 링버퍼 + 형성중 1분봉 ──
    minute_t = (int(now) // 60) * 60
    forming = _forming_minutes.get(code)
    if forming is None or forming["t"] != minute_t:
        if forming is not None:
            ring = _minute_rings.setdefault(
                code, deque(maxlen=TICK_AGG_RING_BUFFER_MAX_MINUTES)
            )
            ring.append(forming)
        forming = {
            "t": minute_t, "open": price, "high": price, "low": price,
            "close": price, "volume": 0,
        }
        _forming_minutes[code] = forming

    forming["high"] = max(forming["high"], price)
    forming["low"] = min(forming["low"], price)
    forming["close"] = price
    forming["volume"] = forming["volume"] + vol_delta


# ────────────────────────────────────────────
# 진행중 봉 파생(1m 링버퍼 + 형성중 1분봉 → 상위 tf 재집계)
# ────────────────────────────────────────────

def _derive_progressing_bucket_from_items(
    ring: list[dict] | None, forming: dict | None, unit_minutes: int
) -> dict | None:
    """candles.resample_items() 재사용(복제 구현 금지) — 마지막 버킷(=진행중)만 취한다.
    순수 함수(전역 상태를 읽지 않음) — 전역 읽기 버전(_derive_progressing_bucket)과
    스냅샷 기반 버전(_progressing_bar_from_snapshot) 이 공유하는 실계산 로직."""
    items: list[dict] = list(ring) if ring else []
    if forming is not None:
        items.append(forming)
    if not items:
        return None
    resampled = candles.resample_items(items, unit_minutes)
    bucket = resampled[-1] if resampled else None
    if bucket is None:
        return None

    # ★ 축소 버킷 가드 — 서버를 장중에 재시작하면 링버퍼가 비어 있으므로, 그 뒤 몇 분치만
    # 담긴 "60분봉"이 만들어진다. 그걸 차트에 내보내면 이력의 **올바른 부분봉을 더 작은
    # 값으로 덮어쓴다**(고가·저가·거래량이 전부 축소된다).
    # 버킷 시작 시각보다 우리가 가진 첫 분봉이 늦으면 앞부분이 빠진 것이므로 내보내지 않는다.
    # 1분봉(unit=1)은 버킷이 곧 그 분 자체라 이 문제가 없다.
    # (1d 는 이 경로를 타지 않는다 — KIS 가 당일 시/고/저를 통째로 주므로 항상 온전하다.)
    if unit_minutes > 1:
        earliest = min((it["t"] for it in items if it.get("t") is not None), default=None)
        if earliest is None or earliest > bucket["t"]:
            return None
    return bucket


def _derive_progressing_bucket(code: str, unit_minutes: int) -> dict | None:
    """전역 상태(_minute_rings/_forming_minutes)를 직접 읽는 경로 — _progressing_bar()
    (테스트가 직접 호출하는 시그니처, 유지 필수) 전용. 스냅샷 기반 일괄 계산(스레드
    안전, asyncio.to_thread 안에서 호출)은 _progressing_bar_from_snapshot 참고."""
    ring = _minute_rings.get(code)
    forming = _forming_minutes.get(code)
    return _derive_progressing_bucket_from_items(ring, forming, unit_minutes)


def _progressing_bar(code: str, tf: str) -> dict | None:
    if tf == "1d":
        return _day_bars.get(code)
    if tf == "1m":
        return _forming_minutes.get(code)
    unit = _UNIT_MINUTES.get(tf)
    if unit is None:
        return None
    return _derive_progressing_bucket(code, unit)


def _snapshot_code(code: str) -> dict:
    """루프 스레드에서 종목 1건의 스냅샷을 뜬다(결함1·2 공통 패턴).

    스레드 안전 불변식(다음 수정자가 깨지 않도록 명시):
      - day_bar: `_day_bars[code]` 는 매 틱마다 새 dict 로 통째 교체되는 패턴
        (_ingest_tick 참고)이라 참조만 들고 있어도 이후 in-place 변형에 노출되지 않는다.
      - ring: `_minute_rings[code]` 의 각 항목(형성 완료된 1분봉)은 링버퍼에 들어간
        뒤로는 절대 변형되지 않는다(불변) — list() 로 얕은 복사만 해도 스레드 안전.
      - forming: `_forming_minutes[code]` 는 매 틱마다 high/low/close/volume 을
        in-place 로 변형한다(_ingest_tick 참고) — 참조만 넘기면 to_thread 안의 계산이
        진행되는 동안 루프 스레드가 값을 바꿔 레이스가 난다. 반드시 dict() 로 얕은
        복사를 떠야 한다.
    스냅샷은 반드시 이 함수처럼 루프 스레드 안에서만 떠야 한다(to_thread 안에서 전역
    상태를 직접 읽지 말 것).
    """
    return {
        "day_bar": _day_bars.get(code),
        "ring": list(_minute_rings[code]) if code in _minute_rings else [],
        "forming": dict(_forming_minutes[code]) if code in _forming_minutes else None,
    }


def _progressing_bar_from_snapshot(snapshot: dict, tf: str) -> dict | None:
    """스냅샷(day_bar/ring/forming 사본)만으로 진행중 봉을 계산한다 — 전역 상태를
    전혀 읽지 않는 순수 함수라 asyncio.to_thread 안에서 스레드 안전하게 호출 가능하다."""
    if tf == "1d":
        return snapshot.get("day_bar")
    if tf == "1m":
        return snapshot.get("forming")
    unit = _UNIT_MINUTES.get(tf)
    if unit is None:
        return None
    return _derive_progressing_bucket_from_items(snapshot.get("ring"), snapshot.get("forming"), unit)


def _bar_has_all_fields(bar: dict) -> bool:
    """결함4: 발행/이력병합 계약은 open/high/low/close/volume 전부 숫자를 요구한다.
    하나라도 None 이면(개장 직후 KIS 빈 필드 등) False — 호출측이 스킵해야 한다."""
    return all(bar.get(k) is not None for k in ("open", "high", "low", "close", "volume"))


def _compute_progressing_bars(snapshots: dict[str, dict]) -> list[tuple[str, str, dict]]:
    """전 종목·전 tf 의 진행중 봉을 일괄 계산하는 순수 헬퍼(결함1) — 모듈 전역 상태를
    전혀 읽지 않고 인자로 받은 스냅샷(dict[code, {day_bar, ring, forming}])만 사용하므로
    asyncio.to_thread 안에서 안전하게 실행 가능하고, 단위 테스트도 가능하다.

    결함4: open/high/low/close/volume 중 하나라도 None 인 봉은 결과에서 제외한다
    ("아직 값이 다 안 찼으면 안 보낸다" 계약).
    """
    out: list[tuple[str, str, dict]] = []
    for code, snapshot in snapshots.items():
        for tf in _ALL_TFS:
            try:
                bar = _progressing_bar_from_snapshot(snapshot, tf)
            except Exception as e:
                logger.warning("[tick_aggregator] 진행중 봉 계산 실패(%s,%s): %s", code, tf, e)
                continue
            if bar is None or not _bar_has_all_fields(bar):
                continue  # 틱이 아직 없거나 필드 미완성 — 보내지 않는다(계약)
            out.append((code, tf, bar))
    return out


def _active_codes(today: str) -> set[str]:
    """당일(KST) 대상 종목만 브로드캐스트·판정 루프 대상으로 삼는다(결함3).

    `_day_bars`/`_forming_minutes` 키 전체를 쓰면: (a) 관심종목에서 빠진 종목도 세션
    내내 대상으로 남고, (b) 다음 거래일 아침 그 종목의 새 틱이 오기 전까지 전일 stale
    1d 봉이 live 로 계속 나간다(롤오버 리셋은 새 틱이 와야 실행되므로). `_last_dates
    [code] == today` 게이트 하나로 (b)는 완전히 막히고 (a)도 다음 거래일부터 자연 소멸한다.

    kis_ws.get_status()["subscribed"] 는 이미 공개 접근자이므로 교집합도 적용해 이탈
    "당일"의 낭비까지 추가로 줄인다(신규 접근자를 kis_ws 에 만들지 않는다 — 지시 준수).
    다만 그 목록이 비어 있으면(부팅 초기 등 일시 상태) 교집합을 건너뛴다 — 이 교집합은
    "추가 최적화"일 뿐이고, 당일 게이트 자체(핵심 결함 (b) 해결)를 무력화하면 안 된다.
    """
    today_codes = {code for code, d in _last_dates.items() if d == today}
    subscribed = set(kis_ws.get_status().get("subscribed", []))
    if not subscribed:
        return today_codes
    return today_codes & subscribed


# ────────────────────────────────────────────
# 소비 태스크 — kis_ws 가 push 하는 이벤트 중 tick 만 골라 ingest
# ────────────────────────────────────────────

async def _consume_loop() -> None:
    assert _stop_event is not None
    assert _queue is not None
    while not _stop_event.is_set():
        try:
            event = await asyncio.wait_for(_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if event.get("type") != "tick":
            # 이 모듈 자신이 내보낸 bar_update, kis_ws 의 status 등 — 같은 큐로
            # 되돌아오므로(add_listener 는 전체 브로드캐스트 대상) 반드시 걸러야 한다.
            continue
        try:
            _ingest_tick(event, time.time())
        except Exception as e:
            logger.warning("[tick_aggregator] 틱 ingest 실패(%s): %s", event.get("code"), e)


# ────────────────────────────────────────────
# 봉 브로드캐스트 태스크(장중에만, 2초 주기)
# ────────────────────────────────────────────

# 송출 루프에서 몇 건마다 asyncio.sleep(0) 을 끼워 WS 송신 태스크에 제어를 넘길지
# (결함1 — 41종목×8tf=최대 328건을 yield 없이 쏟아내면 브라우저 리스너 큐가 넘친다).
_BROADCAST_YIELD_EVERY = 20


async def _broadcast_bars_once() -> None:
    now_dt = datetime.now(ZoneInfo(TIMEZONE))
    if not _is_market_hours(now_dt):
        return  # 장외 — 이번 주기는 건너뜀(브로드캐스트할 새 틱 자체가 없는 게 정상)

    today = _kst_date_str(now_dt.timestamp())
    codes = _active_codes(today)
    if not codes:
        return

    # ① 루프 스레드에서 스냅샷(저렴한 dict 복사만 — _snapshot_code 의 스레드 안전
    #    불변식 주석 참고: day_bar 참조 안전, ring list() 참조 안전, forming dict() 복사 필수).
    snapshots = {code: _snapshot_code(code) for code in codes}

    # ② pandas resample 포함 무거운 계산을 스레드 1회로 위임 — 전 종목·전 tf 일괄 계산.
    try:
        bars = await asyncio.to_thread(_compute_progressing_bars, snapshots)
    except Exception as e:
        logger.warning("[tick_aggregator] 진행중 봉 일괄 계산 실패(이번 주기 건너뜀): %s", e)
        return

    # ③ 송출 — 약 _BROADCAST_YIELD_EVERY 건마다 sleep(0) 으로 WS 송신 태스크가 리스너
    #    큐를 드레인할 기회를 준다.
    for i, (code, tf, bar) in enumerate(bars):
        event = {"type": "bar_update", "code": code, "tf": tf, "bar": bar, "live": True}
        try:
            await kis_ws.broadcast_event(event)
        except Exception as e:
            logger.warning(
                "[tick_aggregator] bar_update 브로드캐스트 실패(%s,%s): %s", code, tf, e
            )
        if (i + 1) % _BROADCAST_YIELD_EVERY == 0:
            await asyncio.sleep(0)


async def _bar_broadcast_loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        await _interruptible_sleep(TICK_AGG_BAR_BROADCAST_INTERVAL_SECONDS)
        if _stop_event.is_set():
            break
        try:
            await _broadcast_bars_once()
        except Exception as e:
            logger.warning("[tick_aggregator] 봉 브로드캐스트 주기 실패(다음 주기 재시도): %s", e)


# ────────────────────────────────────────────
# 참고 판정 태스크(장중에만, 5초 주기)
# ────────────────────────────────────────────

def _financials_for(code: str) -> tuple[float | None, float | None, float | None]:
    """collector 가 이미 수집·캐시해둔 재무값(per/pbr/roe)을 재사용한다 — 참고 판정도
    collector._collect_one 과 동일한 long_term_view/long_term_score 호출 방식(같은 인자
    구성)을 따르되, 재무데이터를 이 모듈에서 다시 조회하지는 않는다(신규 KIS 콜 없음)."""
    state = collector.get_state()
    if state is None:
        return None, None, None
    for item in state.get("items", []):
        if item.get("code") == code:
            return item.get("per"), item.get("pbr"), item.get("roe")
    return None, None, None


def _merge_progressing(history: list[dict], progressing: dict | None) -> list[dict]:
    """확정 이력(t 오름차순) 뒤에 진행중 봉을 이어붙인다.
    이력 마지막 행의 t 가 진행중 봉의 t 와 같으면 교체, 다르면 추가."""
    if progressing is None:
        return history
    if history and history[-1].get("t") == progressing.get("t"):
        return history[:-1] + [progressing]
    return history + [progressing]


def _compute_judgment(
    daily_items: list[dict],
    hour_items: list[dict],
    per: float | None,
    pbr: float | None,
    roe: float | None,
) -> dict:
    """pandas/지표 연산 — 반드시 asyncio.to_thread 로만 호출할 것(이벤트루프 블로킹 금지).

    collector._collect_one 과 동일한 indicators.py 함수·동일한 호출 방식(같은 인자
    순서)을 그대로 따른다 — 판정 기준의 일관성을 위함.
    """
    daily_df = pd.DataFrame(daily_items) if daily_items else pd.DataFrame()
    hour_df = pd.DataFrame(hour_items) if hour_items else pd.DataFrame()

    if daily_df.empty:
        macd_1d = rsi_1d = rules.NO_DATA
    else:
        macd_1d = indicators.macd_cross_signal(daily_df)
        rsi_1d = indicators.rsi_zone_signal(daily_df)

    if hour_df.empty:
        macd_60m = rsi_60m = rules.NO_DATA
    else:
        macd_60m = indicators.macd_cross_signal(hour_df)
        rsi_60m = indicators.rsi_zone_signal(hour_df)

    return {
        "short_view_live": indicators.short_term_view(macd_60m, rsi_60m),
        "short_score_live": indicators.short_term_score(macd_60m, rsi_60m),
        "long_view_live": indicators.long_term_view(macd_1d, rsi_1d, per, pbr, roe),
        "long_score_live": indicators.long_term_score(macd_1d, rsi_1d, per, pbr, roe),
        # 확정 판정과 같은 워밍업 축을 실시간에도 싣는다. 이게 없으면 60분봉이 모자란
        # 종목에서 **확정 칩은 '축적 중'인데 LIVE 칩은 '관망'** 이 뜨는 모순이 생긴다
        # (봉이 모자랄 때 지표가 0점=관망을 내는 성질 때문 — collector.MIN_BARS_60M 참조).
        "bars_60m_live": len(hour_items),
    }


def _reference_worker(
    code: str,
    snapshot: dict,
    per: float | None,
    pbr: float | None,
    roe: float | None,
) -> dict:
    """asyncio.to_thread 전용(결함2) — 동기 SQLite I/O(db.get_candles_store ×2, 호출마다
    sqlite3.connect 를 여는 완전 동기 함수)와 pandas/지표 연산을 전부 이 함수 안에서
    수행해 이벤트루프(uvicorn 워커=1)를 블로킹하지 않는다. day_bar/ring/forming 은 이미
    루프 스레드에서 뜬 스냅샷만 사용하는 순수 함수라 스레드에서 안전하게 돌릴 수 있다.
    """
    daily_hist = db.get_candles_store(code, "1d", 150)
    hour_hist = db.get_candles_store(code, "60m", 150)

    day_bar = snapshot.get("day_bar")
    hour_bar = _progressing_bar_from_snapshot(snapshot, "60m")

    # 결함4: None 필드가 섞인 진행중 봉은 이력에 이어붙이지 않는다 — pandas 지표가
    # NaN 오염되는 것을 막는다(마치 "아직 그 진행중 봉이 없다"인 것처럼 취급).
    if day_bar is not None and not _bar_has_all_fields(day_bar):
        day_bar = None
    if hour_bar is not None and not _bar_has_all_fields(hour_bar):
        hour_bar = None

    daily_items = _merge_progressing(daily_hist, day_bar)
    hour_items = _merge_progressing(hour_hist, hour_bar)

    return _compute_judgment(daily_items, hour_items, per, pbr, roe)


async def _recompute_reference_for_code(code: str, now_dt: datetime) -> None:
    # 루프 스레드에서 스냅샷(_snapshot_code 의 스레드 안전 불변식 주석 참고).
    snapshot = _snapshot_code(code)
    # 인메모리 collector 상태 조회 — DB/pandas 가 아니라 to_thread 밖에 남겨도 무해.
    per, pbr, roe = _financials_for(code)

    judgment = await asyncio.to_thread(_reference_worker, code, snapshot, per, pbr, roe)
    judgment["updated_at"] = now_dt.isoformat()
    _reference_state[code] = judgment  # 종목별 원자 교체(dict 통째 바꿔치기) — 루프 스레드에서


async def _recompute_reference_once() -> None:
    now_dt = datetime.now(ZoneInfo(TIMEZONE))
    if not _is_market_hours(now_dt):
        return  # 장외 — 재계산 skip, 마지막 값 freeze(삭제하지 않음)

    today = _kst_date_str(now_dt.timestamp())
    for code in _active_codes(today):
        try:
            await _recompute_reference_for_code(code, now_dt)
        except Exception as e:
            logger.warning("[tick_aggregator] 참고 판정 계산 실패(%s) — 이번 주기 건너뜀: %s", code, e)


async def _reference_loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        await _interruptible_sleep(TICK_AGG_REFERENCE_INTERVAL_SECONDS)
        if _stop_event.is_set():
            break
        try:
            await _recompute_reference_once()
        except Exception as e:
            logger.warning("[tick_aggregator] 참고 판정 주기 실패(다음 주기 재시도): %s", e)
