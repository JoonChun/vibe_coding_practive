import db
from fastapi import APIRouter, HTTPException

from ..schemas import (
    PaperAccountResponse,
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
