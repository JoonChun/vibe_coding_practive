from fastapi import APIRouter

from ..schemas import SnapshotResponse
from ..services import snapshot_cache

router = APIRouter(prefix="/api")


@router.get("/snapshot", response_model=SnapshotResponse)
async def get_snapshot():
    return await snapshot_cache.get_snapshot()
