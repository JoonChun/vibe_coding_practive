"""KIS WebSocket 세션 매니저 — 실시간체결가(H0STCNT0)를 구독·수신해 브라우저 WS로 중계.

공개 인터페이스(server/routers/stream.py 등 호출측이 이 계약대로 사용):
    - start() / stop(): FastAPI lifespan 에서 각 1회 호출. 내부에서 asyncio 태스크
      (연결 유지 + 60초 구독 갱신)를 기동/정리한다.
    - get_status() -> {"kis_connected": bool, "subscribed": list[str]}
    - add_listener(queue) / remove_listener(queue): 브라우저 WS 핸들러가 자기 전용
      asyncio.Queue(maxsize 등은 호출측이 결정)를 등록/해제해 tick/status 이벤트를
      pull 방식으로 받는다. 등록된 큐가 가득 차면 가장 오래된 항목을 버리고 최신
      이벤트를 넣는다(느린 클라이언트가 전체 브로드캐스트를 막지 않도록).

발행 이벤트(dict, 큐로 push):
    {"type": "tick", "code": str, "price": float, "change": float,
     "change_pct": float, "volume": int | None, "time": "HH:MM:SS"}
    {"type": "status", "kis_connected": bool, "subscribed": list[str]}  (연결 상태 변화 시)

동작 개요:
    1) 연결 태스크(_connection_loop): approval_key 발급(kis_auth.get_approval_key) →
       KIS WS 접속(KIS_WS_URL) → 현재 구독 대상 전 종목 재구독(tr_type="1") → 수신 루프.
       연결이 끊기면 지수 백오프(1초 → 최대 60초)로 재연결하고, 재연결마다
       approval_key 를 다시 확인하고 전 종목을 재구독한다(서버 재기동 시 이전 세션의
       구독 상태를 KIS 서버가 기억하지 않으므로).
    2) 구독 갱신 태스크(_subscription_refresh_loop): 60초마다 db.load_watchlist() 를
       다시 읽어 활성 종목 목록과 현재 목표 목록(diff)만 등록(tr_type="1")/해제
       (tr_type="2") 프레임을 전송한다. 세션당 구독 한도 41건 — 초과분은 앞 41개만
       유지하고 경고 로그를 남긴다.
    3) 수신 프레임 파싱: 첫 글자가 '0'(평문) 또는 '1'(암호화, H0STCNT0 은 KIS 정책상
       평문만 사용되므로 이 모듈은 암호화 프레임은 무시·로그만 남김) → 데이터 프레임.
       그 외 → JSON 제어 메시지(PINGPONG 에코, 구독 등록 rt_cd 로그).

장 외 시간(틱 없음)은 정상 상태다. 이 모듈 내부의 모든 예외는 여기서 격리·로그만
남기고 절대 상위(FastAPI 앱 전체)로 전파하지 않는다 — KIS 쪽 장애가 서버 전체를
죽이면 안 된다.

────────────────────────────────────────────────────────────────────────────
H0STCNT0(국내주식 실시간체결가, KRX) 필드 순서 — 공식 출처(WebFetch로 확인, 추측 아님):
    https://github.com/koreainvestment/open-trading-api
    examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py 의 `columns` 리스트를 그대로 이식.
    (2025-07-09 업데이트 버전 기준. '^' split 결과가 이 순서·개수(46개)와 일치한다.)

    0  MKSC_SHRN_ISCD               유가증권 단축 종목코드
    1  STCK_CNTG_HOUR               주식 체결 시간(HHMMSS)
    2  STCK_PRPR                    주식 현재가
    3  PRDY_VRSS_SIGN               전일 대비 부호
    4  PRDY_VRSS                    전일 대비
    5  PRDY_CTRT                    전일 대비율
    6  WGHN_AVRG_STCK_PRC           가중 평균 주식 가격
    7  STCK_OPRC                    주식 시가
    8  STCK_HGPR                    주식 최고가
    9  STCK_LWPR                    주식 최저가
    10 ASKP1                        매도호가1
    11 BIDP1                        매수호가1
    12 CNTG_VOL                     체결 거래량
    13 ACML_VOL                     누적 거래량
    14 ACML_TR_PBMN                 누적 거래 대금
    (이하 15~45: 이 모듈에서는 사용하지 않음 — 매도/매수 체결건수, 체결강도 등)

    이 모듈이 실제로 쓰는 인덱스는 0(코드), 1(시간), 2(현재가), 3(부호), 4(전일대비),
    5(전일대비율), 13(누적거래량)뿐이다.

    PRDY_VRSS_SIGN(전일 대비 부호) 코드 — KIS REST/WS 전 API 공통 관례:
        1 상한가, 2 상승, 3 보합, 4 하한가, 5 하락.
    (github 예제의 chk_ccnl_krx.py 는 PRDY_VRSS/PRDY_CTRT 를 pd.to_numeric 으로만
    변환하고 별도 부호 반영을 하지 않는다 — 즉 원문 문자열 자체에 부호가 있을 수도
    없을 수도 있다는 뜻이라 확정할 수 없었다. 이중 반전을 막기 위해 이 모듈은
    PRDY_VRSS/PRDY_CTRT 를 abs() 로 절대값 처리한 뒤, 위 부호 코드로 최종 극성을
    결정한다 — 원문에 이미 부호가 있었어도 abs() 가 무력화하므로 안전하다.)

    멀티 레코드(한 프레임에 체결 여러 건, cnt>1): 공식 문서 예시
    "0|H0STCNT0|004|005930^...(1건)...^005930^...(2건)...^..." 대로, '^' split 결과를
    필드 46개 단위로 청크 분할해 cnt 개의 레코드로 나눈다.
────────────────────────────────────────────────────────────────────────────
"""
import asyncio
import contextlib
import json
import logging

import websockets

import db
import kis_auth
from config import KIS_WS_URL

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# 상수
# ────────────────────────────────────────────

_TR_ID_CCNL = "H0STCNT0"
_CCNL_FIELD_COUNT = 46  # 공식 columns 리스트 길이(ccnl_krx.py)

# 필드 인덱스(위 docstring 표와 동일 — 우리가 실제로 쓰는 것만)
_IDX_CODE = 0
_IDX_TIME = 1
_IDX_PRICE = 2
_IDX_SIGN = 3
_IDX_CHANGE = 4
_IDX_CHANGE_PCT = 5
_IDX_VOLUME = 13

# PRDY_VRSS_SIGN 코드 → 극성(1 상한/2 상승 = +, 3 보합 = 0, 4 하한/5 하락 = -)
_SIGN_POLARITY = {"1": 1, "2": 1, "3": 0, "4": -1, "5": -1}

_RECONNECT_BACKOFF_INITIAL_SECONDS = 1
_RECONNECT_BACKOFF_MAX_SECONDS = 60
_CONNECT_OPEN_TIMEOUT_SECONDS = 10

_SUBSCRIPTION_REFRESH_INTERVAL_SECONDS = 60
_MAX_SUBSCRIPTIONS = 41


# ────────────────────────────────────────────
# 모듈 상태
# ────────────────────────────────────────────

_ws = None  # 현재 연결(websockets ClientConnection) — 없으면 None
_connected = False
_target_codes: list[str] = []  # 구독 목표 목록(입력 순서 유지, 41건 캡 적용 후)
_listeners: set[asyncio.Queue] = set()
_tasks: list[asyncio.Task] = []
_stop_event: asyncio.Event | None = None


# ────────────────────────────────────────────
# 공개 인터페이스
# ────────────────────────────────────────────

async def start() -> None:
    """연결 유지 태스크·구독 갱신 태스크를 기동한다. lifespan 에서 1회 호출."""
    global _stop_event
    _stop_event = asyncio.Event()
    _tasks.append(asyncio.create_task(_connection_loop(), name="kis-ws-connection"))
    _tasks.append(
        asyncio.create_task(_subscription_refresh_loop(), name="kis-ws-subscription-refresh")
    )
    logger.info("[kis_ws] 세션 매니저 시작")


async def stop() -> None:
    """모든 내부 태스크를 정리하고 연결을 닫는다. lifespan 종료 시 1회 호출."""
    if _stop_event is not None:
        _stop_event.set()

    for task in list(_tasks):
        await _cancel_task(task)
    _tasks.clear()

    ws = _ws
    if ws is not None:
        with contextlib.suppress(Exception):
            await ws.close()

    global _connected
    _connected = False
    logger.info("[kis_ws] 세션 매니저 정지")


def get_status() -> dict:
    return {"kis_connected": _connected, "subscribed": list(_target_codes)}


def add_listener(queue: asyncio.Queue) -> None:
    _listeners.add(queue)


def remove_listener(queue: asyncio.Queue) -> None:
    _listeners.discard(queue)


# ────────────────────────────────────────────
# 태스크 정리 유틸
# ────────────────────────────────────────────

async def _cancel_task(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning("[kis_ws] 태스크 정리 중 예외(무시하고 계속): %s", e)


async def _interruptible_sleep(seconds: float) -> None:
    """seconds 만큼 대기하되, stop() 이 호출되면 즉시 깨어난다."""
    if _stop_event is None:
        await asyncio.sleep(seconds)
        return
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(_stop_event.wait(), timeout=seconds)


# ────────────────────────────────────────────
# 브로드캐스트(리스너 큐로 push) — 느린 클라이언트가 막지 않도록 drop-oldest.
# ────────────────────────────────────────────

def _put_nowait_drop_oldest(queue: asyncio.Queue, event: dict) -> None:
    try:
        queue.put_nowait(event)
        return
    except asyncio.QueueFull:
        pass

    try:
        queue.get_nowait()
    except asyncio.QueueEmpty:
        pass

    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        # 극단적 동시성 상황(다른 태스크가 그 사이 다시 채움) — 이번 이벤트만 드롭.
        pass


async def _broadcast(event: dict) -> None:
    for queue in list(_listeners):
        _put_nowait_drop_oldest(queue, event)


async def _broadcast_status() -> None:
    await _broadcast({"type": "status", **get_status()})


# ────────────────────────────────────────────
# H0STCNT0 파싱
# ────────────────────────────────────────────

def _format_time(raw_time: str) -> str:
    if len(raw_time) == 6 and raw_time.isdigit():
        return f"{raw_time[0:2]}:{raw_time[2:4]}:{raw_time[4:6]}"
    return raw_time


def _parse_ccnl_record(fields: list[str]) -> dict | None:
    """H0STCNT0 레코드(46필드) 1건을 tick 이벤트 dict로 변환. 파싱 실패 시 None."""
    if len(fields) < _CCNL_FIELD_COUNT:
        return None

    try:
        code = fields[_IDX_CODE].strip()
        if not code:
            return None
        raw_time = fields[_IDX_TIME].strip()
        price = float(fields[_IDX_PRICE])
        sign = fields[_IDX_SIGN].strip()
        change_magnitude = abs(float(fields[_IDX_CHANGE])) if fields[_IDX_CHANGE] else 0.0
        change_pct_magnitude = (
            abs(float(fields[_IDX_CHANGE_PCT])) if fields[_IDX_CHANGE_PCT] else 0.0
        )
        volume_raw = fields[_IDX_VOLUME]
        volume = int(float(volume_raw)) if volume_raw else None
    except (ValueError, IndexError):
        return None

    polarity = _SIGN_POLARITY.get(sign, 0)

    return {
        "type": "tick",
        "code": code,
        "price": price,
        "change": round(change_magnitude * polarity, 2),
        "change_pct": round(change_pct_magnitude * polarity, 2),
        "volume": volume,
        "time": _format_time(raw_time),
    }


def _handle_data_frame(raw: str) -> list[dict]:
    """평문/암호화 데이터 프레임('0|...' 또는 '1|...') 을 tick 이벤트 리스트로 변환.

    형식: {encrypt_flag}|{tr_id}|{cnt}|{'^' 로 구분된 필드, cnt>1 이면 46필드씩 연속}
    (공식 문서 예시: "0|H0STCNT0|004|005930^...^005930^...^...")
    """
    parts = raw.split("|")
    if len(parts) < 4:
        logger.warning("[kis_ws] 데이터 프레임 형식 이상(필드 부족): %.200s", raw)
        return []

    encrypt_flag, tr_id, cnt_str, body = parts[0], parts[1], parts[2], parts[3]

    if tr_id != _TR_ID_CCNL:
        return []  # 구독 대상 외 tr_id — 스코프 확대 없이 무시

    if encrypt_flag == "1":
        # H0STCNT0 은 KIS 정책상 평문 전송만 사용하므로 암호화 프레임은 다루지 않는다.
        logger.warning("[kis_ws] 예상치 못한 암호화 데이터 프레임 수신 — 무시: tr_id=%s", tr_id)
        return []

    try:
        cnt = max(int(cnt_str), 1)
    except ValueError:
        cnt = 1

    all_fields = body.split("^")
    events: list[dict] = []
    for i in range(cnt):
        start = i * _CCNL_FIELD_COUNT
        end = start + _CCNL_FIELD_COUNT
        record_fields = all_fields[start:end]
        if not record_fields:
            break
        event = _parse_ccnl_record(record_fields)
        if event is not None:
            events.append(event)
    return events


async def _handle_control_frame(ws, raw: str) -> None:
    """JSON 제어 메시지(PINGPONG, 구독 등록/해제 응답) 처리."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[kis_ws] JSON 파싱 실패(제어 메시지 아님?): %.200s", raw)
        return

    header = payload.get("header") or {}
    tr_id = header.get("tr_id")

    if tr_id == "PINGPONG":
        try:
            await ws.pong(raw)
        except Exception as e:
            logger.warning("[kis_ws] PINGPONG 응답 실패: %s", e)
        return

    body = payload.get("body")
    if body is None:
        return

    rt_cd = body.get("rt_cd")
    msg1 = body.get("msg1")
    if rt_cd == "0":
        logger.info("[kis_ws] 구독 응답 성공: tr_id=%s msg=%s", tr_id, msg1)
    else:
        logger.warning("[kis_ws] 구독 응답 실패: tr_id=%s rt_cd=%s msg=%s", tr_id, rt_cd, msg1)


# ────────────────────────────────────────────
# 구독 프레임 송신
# ────────────────────────────────────────────

def _build_frame(approval_key: str, tr_type: str, code: str) -> str:
    frame = {
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": tr_type,
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": _TR_ID_CCNL,
                "tr_key": code,
            }
        },
    }
    return json.dumps(frame)


async def _send_subscribe(ws, approval_key: str, code: str) -> None:
    await ws.send(_build_frame(approval_key, "1", code))


async def _send_unsubscribe(ws, approval_key: str, code: str) -> None:
    await ws.send(_build_frame(approval_key, "2", code))


async def _resubscribe_all(ws, approval_key: str) -> None:
    """새 연결 직후 목표 종목 전체를 재구독(KIS 서버는 연결 단위로 구독 상태를 갖는다)."""
    for code in _target_codes:
        try:
            await _send_subscribe(ws, approval_key, code)
        except Exception as e:
            logger.warning("[kis_ws] 재구독 실패(%s): %s", code, e)


# ────────────────────────────────────────────
# 구독 갱신 태스크 — 60초마다 watchlist 재확인, diff 만 등록/해제
# ────────────────────────────────────────────

async def _refresh_subscriptions() -> None:
    global _target_codes

    try:
        stock_list = await asyncio.to_thread(db.load_watchlist)
    except Exception as e:
        logger.warning("[kis_ws] watchlist 로드 실패 — 이번 주기 구독 갱신 건너뜀: %s", e)
        return

    codes: list[str] = []
    seen: set[str] = set()
    for item in stock_list:
        code = item.get("code")
        if code and code not in seen:
            seen.add(code)
            codes.append(code)

    if len(codes) > _MAX_SUBSCRIPTIONS:
        logger.warning(
            "[kis_ws] 관심종목 %d건이 세션 구독 한도(%d건)를 초과 — 앞 %d개만 구독",
            len(codes), _MAX_SUBSCRIPTIONS, _MAX_SUBSCRIPTIONS,
        )
        codes = codes[:_MAX_SUBSCRIPTIONS]

    previous = set(_target_codes)
    current = set(codes)
    added = current - previous
    removed = previous - current

    _target_codes = codes

    ws = _ws
    if ws is None or not _connected:
        return  # 미연결 동안은 목표 목록만 갱신 — 재연결 시 _resubscribe_all 이 전체 반영

    if not added and not removed:
        return

    try:
        approval_key = await asyncio.to_thread(kis_auth.get_approval_key)
    except Exception as e:
        logger.warning("[kis_ws] 구독 갱신용 approval_key 조회 실패: %s", e)
        return

    for code in removed:
        try:
            await _send_unsubscribe(ws, approval_key, code)
        except Exception as e:
            logger.warning("[kis_ws] 구독 해제 실패(%s): %s", code, e)

    for code in added:
        try:
            await _send_subscribe(ws, approval_key, code)
        except Exception as e:
            logger.warning("[kis_ws] 구독 등록 실패(%s): %s", code, e)

    logger.info(
        "[kis_ws] 구독 갱신 완료 — 추가 %d건, 해제 %d건(총 %d건 구독 중)",
        len(added), len(removed), len(_target_codes),
    )


async def _subscription_refresh_loop() -> None:
    assert _stop_event is not None
    await _refresh_subscriptions()  # 최초 1회 즉시
    while not _stop_event.is_set():
        await _interruptible_sleep(_SUBSCRIPTION_REFRESH_INTERVAL_SECONDS)
        if _stop_event.is_set():
            break
        try:
            await _refresh_subscriptions()
        except Exception as e:
            logger.warning("[kis_ws] 구독 갱신 주기 실패(다음 주기에 재시도): %s", e)


# ────────────────────────────────────────────
# 연결 유지 태스크 — 지수 백오프 재연결
# ────────────────────────────────────────────

async def _read_loop(ws) -> None:
    async for raw in ws:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not raw:
            continue

        # 프레임 단위로 예외를 격리 — 파싱 이상 1건이 연결 전체를 끊고 재연결을
        # 유발하지 않도록(연결 유지가 훨씬 저렴하다). 연결 자체가 끊기는 예외
        # (ConnectionClosed 등)는 async for 이터레이터가 알아서 루프를 끝낸다.
        try:
            if raw[0] in ("0", "1"):
                events = _handle_data_frame(raw)
                for event in events:
                    await _broadcast(event)
            else:
                await _handle_control_frame(ws, raw)
        except Exception as e:
            logger.warning("[kis_ws] 프레임 처리 중 예외(연결 유지, 계속 진행): %s", e)


async def _connection_loop() -> None:
    assert _stop_event is not None
    global _ws, _connected

    backoff = _RECONNECT_BACKOFF_INITIAL_SECONDS

    while not _stop_event.is_set():
        try:
            approval_key = await asyncio.to_thread(kis_auth.get_approval_key)
        except Exception as e:
            logger.warning(
                "[kis_ws] approval_key 발급 실패 — %d초 후 재시도: %s", backoff, e
            )
            await _interruptible_sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_BACKOFF_MAX_SECONDS)
            continue

        try:
            # ping_interval=None: KIS 서버가 WS 프로토콜 레벨 Ping/Pong에 응답한다는
            # 보장이 없어(공식 예제도 JSON PINGPONG 에코만 사용), websockets 기본값
            # (20초 간격 ping, 20초 응답 대기)을 켜두면 정상 연결도 약 40초마다 pong
            # 미수신으로 강제 종료될 위험이 있다. 이 모듈은 위 _handle_control_frame의
            # JSON PINGPONG 에코로 KIS 세션 유지를 이미 전담하므로 프로토콜 레벨
            # keepalive는 끈다.
            ws = await websockets.connect(
                KIS_WS_URL,
                open_timeout=_CONNECT_OPEN_TIMEOUT_SECONDS,
                ping_interval=None,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(
                "[kis_ws] KIS WebSocket 접속 실패 — %d초 후 재시도: %s", backoff, e
            )
            await _interruptible_sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_BACKOFF_MAX_SECONDS)
            continue

        _ws = ws
        logger.info("[kis_ws] KIS WebSocket 연결 성공")

        try:
            await _resubscribe_all(ws, approval_key)
            _connected = True
            await _broadcast_status()
            backoff = _RECONNECT_BACKOFF_INITIAL_SECONDS

            await _read_loop(ws)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[kis_ws] KIS WebSocket 연결 끊김/오류: %s", e)
        finally:
            with contextlib.suppress(Exception):
                await ws.close()
            _ws = None
            if _connected:
                _connected = False
                await _broadcast_status()

        if _stop_event.is_set():
            break

        await _interruptible_sleep(backoff)
        backoff = min(backoff * 2, _RECONNECT_BACKOFF_MAX_SECONDS)

    logger.info("[kis_ws] 연결 루프 종료")
