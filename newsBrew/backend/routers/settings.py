import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from database.database import get_db
from database.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SECRET_KEYS = {"serpapi_key", "openai_key", "resend_key", "google_service_account_json"}
_SCHEDULE_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class SettingsPayload(BaseModel):
    schedule_time: str = "08:00"
    serpapi_key: str = ""
    openai_key: str = ""
    resend_key: str = ""
    recipient_emails: str = ""
    google_sheet_id: str = ""
    google_service_account_json: str = ""

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time(cls, v: str) -> str:
        if not _SCHEDULE_RE.match(v):
            raise ValueError("schedule_time must be in HH:MM format (00:00–23:59)")
        return v


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    rows = result.scalars().all()
    return {
        r.key: ("***" if r.key in _SECRET_KEYS and r.value else r.value)
        for r in rows
    }


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

    from services.scheduler import setup_scheduler
    setup_scheduler(body.schedule_time)

    return {"status": "success"}
