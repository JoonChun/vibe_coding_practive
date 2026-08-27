"""브라우저 실시간 시세 WS 라우트 — WS /ws/ticks.

KIS 실시간 체결 데이터를 브라우저로 중계하는 창구다. 실제 KIS WS 연결·재연결·
구독 관리는 server/services/kis_ws.py 가 전담하며(Phase 2 계약), 이 라우터는
그 모듈의 공개 인터페이스(add_listener/remove_listener/get_status)만 사용한다
— kis_ws 내부 프로토콜(approval_key, 프레임 파싱 등)에는 관여하지 않는다.

인증 참고:
  server/auth.py 의 auth_middleware 는 Starlette BaseHTTPMiddleware 라
  scope type == "http" 요청에만 적용되고 WebSocket 핸드셰이크(scope type
  == "websocket")는 애초에 그 미들웨어를 통과하지 않는다. 따라서 여기서
  라우트 자체적으로 ?token= 쿼리 파라미터를 검증한다(계약 명시 사항).
"""
import asyncio
import contextlib
import logging
import os

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from config import API_TOKEN_ENV_KEY

from ..auth import tokens_match
from ..services import kis_ws

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])

# 느린 클라이언트가 전체 브로드캐스트를 막지 않도록 유한 큐(가득 차면 kis_ws 쪽에서
# 가장 오래된 항목을 drop — 계약: add_listener(q) 를 등록만 하면 됨).
# 진행중 봉 브로드캐스트가 붙으면서 한 주기에 최대 41종목 × 8tf ≈ 328건이 몰린다.
# 200 이면 앞쪽 종목이 drop-oldest 로 유실되므로 여유를 크게 둔다.
_QUEUE_MAXSIZE = 2000

# 토큰 불일치 시 종료 코드. 4000~4999 는 애플리케이션 전용 대역(RFC 6455).
_CLOSE_CODE_UNAUTHORIZED = 4401

# auth.py 와 동일한 관례: 모듈 로드(=앱 시작) 시 1회만 환경변수를 읽는다.
_API_TOKEN = os.environ.get(API_TOKEN_ENV_KEY, "").strip() or None


def _is_authorized(token: str | None) -> bool:
    """MYSTOCKBOT_API_TOKEN 미설정 시 자유 접속, 설정 시 상수시간 비교로 검증.

    비교는 `auth.tokens_match` 에 위임한다 — `secrets.compare_digest` 를 `str` 로
    직접 부르면 비ASCII 토큰에서 TypeError 가 나고, 여기서는 그게 4401(인증 실패)이
    아니라 핸드셰이크 예외가 된다. HTTP 쪽과 **같은 함수**를 쓰게 해서 한쪽만 고쳐지는
    상황을 막는다.
    """
    if _API_TOKEN is None:
        return True
    if not token:
        return False
    return tokens_match(token, _API_TOKEN)


async def _drain_incoming(websocket: WebSocket) -> None:
    """클라이언트→서버 방향으로는 프로토콜상 아무 메시지도 기대하지 않는다.

    이 태스크의 목적은 순전히 "클라이언트가 연결을 끊었다"는 사실을 감지하는 것
    — 송신 전용 루프만 돌리면 상대가 끊어도 서버가 즉시 알아채지 못해 좀비
    커넥션이 남을 수 있어, receive 를 병행 대기시켜 WebSocketDisconnect 로
    깨어나게 한다(FastAPI/Starlette 공식 예제와 동일한 패턴).
    """
    while True:
        await websocket.receive_text()


@router.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket, token: str | None = Query(default=None)):
    if not _is_authorized(token):
        # 계약: 거절 시에도 accept 후 close(4401) — 브라우저 WS 클라이언트가
        # 핸드셰이크 단계 거부보다 명시적 close 코드를 다루기 수월하다.
        await websocket.accept()
        await websocket.close(code=_CLOSE_CODE_UNAUTHORIZED)
        return

    await websocket.accept()

    queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    kis_ws.add_listener(queue)

    reader_task = asyncio.create_task(_drain_incoming(websocket))
    try:
        status = kis_ws.get_status()
        await websocket.send_json({"type": "status", **status})

        while True:
            get_task = asyncio.create_task(queue.get())
            done, _pending = await asyncio.wait(
                {reader_task, get_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if reader_task in done:
                get_task.cancel()
                # _drain_incoming 은 무한루프라 정상 반환은 없다 — 여기 도달했다는 것 자체가
                # WebSocketDisconnect(또는 다른 예외)로 끝났다는 뜻. result() 로 재-raise해
                # 아래 except 절이 그대로 처리하게 한다.
                reader_task.result()
                break
            await websocket.send_json(get_task.result())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # 개별 연결의 예외가 서버 전체(다른 연결·수집 루프)에 번지면 안 된다.
        logger.warning(f"[stream] /ws/ticks 처리 중 예외: {e}")
    finally:
        # reader_task 는 두 경로로 여기 도달할 수 있다:
        #  ① 아직 진행 중(정상 송신 루프 중 다른 예외로 빠져나옴) → cancel() 후
        #     await 하면 asyncio.CancelledError 가 난다.
        #  ② 이미 disconnect 예외로 완료됨(위에서 result() 로 이미 재-raise 했던 것) →
        #     다시 await 하면 동일 예외(Exception 계열, 예: WebSocketDisconnect)가 재발생.
        # 둘 다 "이미 처리(또는 처리 불필요)된" 예외이므로 정리 목적으로만 흡수한다.
        reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await reader_task
        kis_ws.remove_listener(queue)
