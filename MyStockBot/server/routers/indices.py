import asyncio

from fastapi import APIRouter

from ..schemas import IndicesResponse
from ..services import indices as indices_service

router = APIRouter(prefix="/api")


@router.get("/indices", response_model=IndicesResponse)
async def get_indices():
    # indices_service.get_indices() 는 blocking HTTP 호출을 포함하므로 스레드로 오프로드
    # (routers/stocks.py 의 candles 조회와 동일 패턴).
    return await asyncio.to_thread(indices_service.get_indices)
