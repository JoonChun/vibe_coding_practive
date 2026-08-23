import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

import db
import watchlist_sync

from ..services import candles

from ..schemas import (
    WatchlistItemIn,
    WatchlistItemOut,
    WatchlistListResponse,
    WatchlistSyncResponse,
)

router = APIRouter(prefix="/api")


@router.get("/watchlist", response_model=WatchlistListResponse)
def get_watchlist():
    return {"items": db.load_watchlist()}


@router.post("/watchlist", response_model=WatchlistItemOut, status_code=201)
def create_watchlist_item(item: WatchlistItemIn, background_tasks: BackgroundTasks):
    try:
        row = db.add_watchlist_item(item.code, item.name)
    except db.DuplicateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # 앱 → 시트 미러링(단일 소스화). 응답을 막지 않도록 백그라운드로 보내고, 실패해도
    # 앱 목록은 이미 갱신된 상태다(watchlist_sync 가 예외를 격리하고 로그만 남긴다).
    background_tasks.add_task(watchlist_sync.mirror_add, row["code"], row["name"])
    # 일/주/월봉 과거 이력 선채움 — 첫 차트 조회의 온디맨드 딥 수집(페이지네이션 수 초)을
    # 사용자가 기다리지 않게 한다. 실패해도 온디맨드 경로가 그대로 남아 있다.
    background_tasks.add_task(candles.backfill_history, row["code"])
    return row


@router.delete("/watchlist/{code}", status_code=204)
def delete_watchlist_item(code: str, background_tasks: BackgroundTasks):
    try:
        removed = db.remove_watchlist_item(code)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not removed:
        raise HTTPException(status_code=404, detail=f"종목을 찾을 수 없습니다: {code}")
    # 시트 쪽은 행을 지우지 않고 C열에 '해제' 표시만 남긴다(사용자 입력 보존).
    background_tasks.add_task(watchlist_sync.mirror_remove, db.normalize_code(code))
    return Response(status_code=204)


@router.post("/watchlist/sync", response_model=WatchlistSyncResponse)
async def sync_watchlist_from_sheet():
    """시트 Dashboard → 앱 관심종목 임포트를 즉시 실행(추가 전용).

    스케줄러(평일 매시 :50)를 기다리지 않고 수렴시키거나, 동기화 활성 여부를 확인할 때 쓴다.
    gspread 호출은 블로킹이므로 스레드로 오프로드한다.
    """
    return await asyncio.to_thread(watchlist_sync.import_from_sheet)
