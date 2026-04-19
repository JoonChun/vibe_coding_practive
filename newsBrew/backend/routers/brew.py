import asyncio
from fastapi import APIRouter
from services.brew_orchestrator import run_brew_pipeline

router = APIRouter(prefix="/api/brew", tags=["brew"])

_brew_tasks: set[asyncio.Task] = set()


@router.post("/start")
async def start_brew():
    task = asyncio.create_task(run_brew_pipeline())
    _brew_tasks.add(task)
    task.add_done_callback(_brew_tasks.discard)
    return {"status": "started"}
