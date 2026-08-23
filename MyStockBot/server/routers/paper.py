import db
from fastapi import APIRouter, HTTPException

from ..schemas import (
    PaperAccountResponse,
    PaperEquityResponse,
    PaperOrderRequest,
    PaperTradesResponse,
)
from ..services import paper as paper_service

router = APIRouter(prefix="/api")


@router.get("/paper/account", response_model=PaperAccountResponse)
def get_account():
    return paper_service.get_account()


@router.get("/paper/trades", response_model=PaperTradesResponse)
def get_trades(limit: int = 100):
    return paper_service.get_trades(limit)


@router.post("/paper/orders", response_model=PaperAccountResponse)
def place_order(order: PaperOrderRequest):
    try:
        return paper_service.place_order(order.code, order.side, order.qty)
    except (db.InvalidOrderError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except db.InsufficientFundsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except paper_service.PriceUnavailableError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/paper/reset", response_model=PaperAccountResponse)
def reset_account():
    return paper_service.reset()


@router.get("/paper/equity", response_model=PaperEquityResponse)
def get_equity():
    """자산 추이 — 거래 이력 replay + 일봉 종가로 일자별 평가금액 재구성.

    거래 이력·일봉 저장소 조회(SQLite)만 하는 블로킹 로직이라 def 핸들러 그대로 둔다
    (외부 네트워크 호출 없음 — 다른 paper 라우트와 동일 관례).
    """
    return paper_service.get_equity_curve()
