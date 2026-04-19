import asyncio
from fastapi import APIRouter
from services.brew_orchestrator import run_brew_pipeline

router = APIRouter(prefix="/api/brew", tags=["brew"])

@router.post("/start")
async def start_brew():
    asyncio.create_task(run_brew_pipeline())
    return {"status": "started"}
