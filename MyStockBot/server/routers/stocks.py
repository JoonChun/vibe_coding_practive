import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

import db

from ..schemas import BarsResponse, CandlesResponse, SearchResponse
from ..services import candles

router = APIRouter(prefix="/api")

_DEFAULT_BARS_LIMIT = 30
_MAX_BARS_LIMIT = 120

_DEFAULT_SEARCH_LIMIT = 10
_MAX_SEARCH_LIMIT = 30

_DEFAULT_CANDLES_COUNT = 150
_MAX_CANDLES_COUNT = 300

# 화이트리스트 겸 FastAPI/Pydantic 자동 422 검증용 Literal.
CandleTf = Literal["1m", "5m", "15m", "30m", "60m", "120m", "240m", "1d", "1w", "1M", "1y"]


@router.get("/stocks/search", response_model=SearchResponse)
def search_stocks(
    q: str = Query(default=""),
    limit: int = Query(default=_DEFAULT_SEARCH_LIMIT, ge=1, le=_MAX_SEARCH_LIMIT),
):
    # q 없거나 공백이면 db.search_stocks 가 빈 리스트를 반환(422/500 아님).
    # 마스터 테이블이 비어 있어도 동일하게 빈 리스트.
    items = db.search_stocks(q, limit)
    return {"items": items}


@router.get("/stocks/{code}/bars", response_model=BarsResponse)
def get_stock_bars(
    code: str,
    limit: int = Query(default=_DEFAULT_BARS_LIMIT, ge=1, le=_MAX_BARS_LIMIT),
):
    try:
        normalized_code = db.normalize_code(code)
        items = db.get_bar_history(normalized_code, limit)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"code": normalized_code, "items": items}


@router.get("/stocks/{code}/candles", response_model=CandlesResponse)
async def get_stock_candles(
    code: str,
    tf: CandleTf = Query(default="1d"),
    count: int = Query(default=_DEFAULT_CANDLES_COUNT, ge=1, le=_MAX_CANDLES_COUNT),
):
    # tf 는 CandleTf(Literal)로 FastAPI가 이미 화이트리스트 검증(위반 시 자동 422)한다.
    try:
        normalized_code = db.normalize_code(code)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # KIS/yfinance 네트워크 호출은 블로킹이므로 스레드로 넘겨 이벤트루프를 막지 않는다.
    result = await asyncio.to_thread(candles.get_candles, normalized_code, tf, count)
    return result
