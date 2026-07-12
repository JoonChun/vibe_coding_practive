from fastapi import APIRouter, HTTPException, Response

import db

from ..schemas import WatchlistItemIn, WatchlistItemOut, WatchlistListResponse

router = APIRouter(prefix="/api")


@router.get("/watchlist", response_model=WatchlistListResponse)
def get_watchlist():
    return {"items": db.load_watchlist()}


@router.post("/watchlist", response_model=WatchlistItemOut, status_code=201)
def create_watchlist_item(item: WatchlistItemIn):
    try:
        row = db.add_watchlist_item(item.code, item.name)
    except db.DuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return row


@router.delete("/watchlist/{code}", status_code=204)
def delete_watchlist_item(code: str):
    try:
        removed = db.remove_watchlist_item(code)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not removed:
        raise HTTPException(status_code=404, detail=f"종목을 찾을 수 없습니다: {code}")
    return Response(status_code=204)
