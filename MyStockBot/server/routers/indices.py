import asyncio

from fastapi import APIRouter, Response

from ..schemas import IndicesResponse
from ..services import indices as indices_service

router = APIRouter(prefix="/api")


@router.get("/indices", response_model=IndicesResponse)
async def get_indices(response: Response):
    # 브라우저·중간 프록시가 이 응답을 재사용하면 안 된다.
    #
    # 서버는 이미 지수별 read-through 캐시를 갖고 있고(성공 60초 / 실패 10초),
    # **실패와 stale 을 짧은 수명으로 관리하는 것이 이 엔드포인트의 핵심 계약이다.**
    # 클라이언트가 응답을 캐시해 버리면 그 계약이 무의미해진다 — 실패 응답이 클라이언트
    # 쪽에 눌러앉아, 서버가 10초 뒤 복구된 값을 내줄 준비가 돼 있어도 화면은 계속 실패를
    # 보여준다(사용자가 새로고침해도 마찬가지). 시세성 데이터라 조건부 요청도 의미가 없다.
    response.headers["Cache-Control"] = "no-store"

    # indices_service.get_indices() 는 blocking HTTP 호출을 포함하므로 스레드로 오프로드
    # (routers/stocks.py 의 candles 조회와 동일 패턴).
    return await asyncio.to_thread(indices_service.get_indices)
