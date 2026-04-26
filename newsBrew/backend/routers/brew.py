import asyncio
from datetime import date
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from database.database import AsyncSessionLocal
from database.models import Setting
from services.brew_orchestrator import run_brew_pipeline
from services.email_sender import send_brew_email
from services.ai_brewer import BrewedArticle

router = APIRouter(prefix="/api/brew", tags=["brew"])

_brew_tasks: set[asyncio.Task] = set()
_is_brewing = False


@router.post("/start")
async def start_brew():
    global _is_brewing
    if _is_brewing:
        raise HTTPException(status_code=409, detail="브루잉이 이미 진행 중입니다.")

    _is_brewing = True

    async def _run_and_reset():
        global _is_brewing
        try:
            await run_brew_pipeline()
        finally:
            _is_brewing = False

    task = asyncio.create_task(_run_and_reset())
    _brew_tasks.add(task)
    task.add_done_callback(_brew_tasks.discard)
    return {"status": "started"}


@router.get("/status")
async def brew_status():
    return {"is_brewing": _is_brewing}


@router.post("/test-email")
async def test_email():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Setting))
        settings = {r.key: r.value for r in result.scalars().all()}

    resend_key = settings.get("resend_key", "")
    recipient_emails = settings.get("recipient_emails", "")

    if not resend_key:
        raise HTTPException(status_code=400, detail="resend_key가 설정되지 않았습니다.")
    if not recipient_emails:
        raise HTTPException(status_code=400, detail="recipient_emails가 설정되지 않았습니다.")

    dummy_articles = [
        BrewedArticle(
            title="[테스트] News Brew 이메일 발송 테스트",
            url="https://example.com",
            source="News Brew",
            published_at="2026-04-19",
            summary="이 메일은 News Brew 이메일 발송 기능 테스트입니다. 실제 뉴스가 아닙니다.",
            importance_score=9,
        )
    ]

    try:
        await send_brew_email(
            api_key=resend_key,
            recipient_emails=recipient_emails,
            brew_date=date.today().isoformat(),
            keyword_results={"테스트": dummy_articles},
        )
        return {"status": "success", "to": recipient_emails}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
