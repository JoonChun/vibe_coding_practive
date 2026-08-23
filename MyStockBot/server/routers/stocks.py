import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

import db

from ..schemas import BacktestResponse, CandlesResponse, DcaResponse, SearchResponse
from ..services import backtest, candles, dca
from ..services.timeseries import PriceDataError

router = APIRouter(prefix="/api")

_DEFAULT_SEARCH_LIMIT = 10
_MAX_SEARCH_LIMIT = 30

_DEFAULT_CANDLES_COUNT = 150
# Query 단계에서는 전 tf 공통 상한(1d/1w/60m/120m/240m의 확장 상한 1000)만 검증한다.
# tf별 실제 상한(1d/1w/60m/120m/240m=1000, 그 외=300)은 candles.get_candles() 내부에서
# 조용히 clamp한다(기존 계약).
_MAX_CANDLES_COUNT = 1000

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


@router.get("/stocks/{code}/candles", response_model=CandlesResponse)
async def get_stock_candles(
    code: str,
    tf: CandleTf = Query(default="1d"),
    count: int = Query(default=_DEFAULT_CANDLES_COUNT, ge=1, le=_MAX_CANDLES_COUNT),
    # before: 이 epoch(초) 미만(t < before)의 과거 구간만 조회 — 차트 왼쪽 스크롤
    # 무한 로딩용 커서. 프론트가 이미 가진 가장 오래된 봉의 t 를 그대로 넘긴다.
    before: int | None = Query(default=None, ge=1),
):
    # tf 는 CandleTf(Literal)로 FastAPI가 이미 화이트리스트 검증(위반 시 자동 422)한다.
    try:
        normalized_code = db.normalize_code(code)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # KIS/yfinance 네트워크 호출은 블로킹이므로 스레드로 넘겨 이벤트루프를 막지 않는다.
    result = await asyncio.to_thread(candles.get_candles, normalized_code, tf, count, before)
    return result


@router.get("/stocks/{code}/backtest", response_model=BacktestResponse)
async def get_stock_backtest(
    code: str,
    horizon: int = Query(default=20, ge=5, le=120),
):
    try:
        normalized_code = db.normalize_code(code)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        # 지표 재계산(CPU) + 데이터 로드(블로킹)를 스레드로 오프로드
        return await asyncio.to_thread(backtest.signal_backtest, normalized_code, horizon)
    except backtest.InsufficientHistoryError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PriceDataError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/stocks/{code}/dca", response_model=DcaResponse)
async def get_stock_dca(
    code: str,
    mode: Literal["qty", "amount"] = Query(default="qty"),
    per: float = Query(default=1, gt=0),
    months: int = Query(default=120, ge=6, le=240),
    freq: Literal["weekly", "monthly", "quarterly"] = Query(default="monthly"),
    reinvest: bool = Query(default=False),
):
    try:
        normalized_code = db.normalize_code(code)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        return await asyncio.to_thread(
            dca.dca_backtest, normalized_code, mode, per, months, freq, reinvest
        )
    except dca.InsufficientHistoryError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except dca.DataSourceError as e:
        raise HTTPException(status_code=503, detail=str(e))
