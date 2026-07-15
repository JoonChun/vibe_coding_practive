from fastapi import APIRouter, HTTPException, Query

import db

from ..schemas import BarsResponse, SearchResponse

router = APIRouter(prefix="/api")

_DEFAULT_BARS_LIMIT = 30
_MAX_BARS_LIMIT = 120

_DEFAULT_SEARCH_LIMIT = 10
_MAX_SEARCH_LIMIT = 30


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
