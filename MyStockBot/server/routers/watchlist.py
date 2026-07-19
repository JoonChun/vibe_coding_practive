from fastapi import APIRouter, HTTPException, Response

import db

from ..schemas import WatchlistItemIn, WatchlistItemOut, WatchlistListResponse
from ..services import collector

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

    # 신규 종목은 다음 정기 사이클(최대 COLLECTOR_INTERVAL_*)까지 기다리지 않고 즉시
    # 수집을 앞당긴다. 트리거 실패는 201 응답을 막지 않는다(있으면 좋은 UX, 필수 아님).
    try:
        collector.trigger_immediate_cycle()
    except Exception as e:
        print(f"[watchlist] 즉시 수집 트리거 실패(무시, 다음 정기 사이클에서 반영됨): {e}")

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
