from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database.database import get_db
from database.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTING_KEYS = [
    "schedule_time", "serpapi_key", "openai_key", "resend_key",
    "recipient_emails", "google_sheet_id", "google_service_account_json"
]

class SettingsPayload(BaseModel):
    schedule_time: str = "08:00"
    serpapi_key: str = ""
    openai_key: str = ""
    resend_key: str = ""
    recipient_emails: str = ""
    google_sheet_id: str = ""
    google_service_account_json: str = ""

@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}

@router.post("")
async def save_settings(body: SettingsPayload, db: AsyncSession = Depends(get_db)):
    for key, value in body.model_dump().items():
        result = await db.execute(select(Setting).where(Setting.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            db.add(Setting(key=key, value=value))
    await db.commit()
    return {"status": "success"}
