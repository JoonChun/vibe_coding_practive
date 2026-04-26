import re
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from database.database import get_db
from database.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

# 시크릿 키 목록 - 단일 정의 지점 (email_sender.py는 이 모듈에서 import)
SECRET_KEYS: frozenset[str] = frozenset({
    "serpapi_key",
    "openai_key",
    "resend_key",
    "google_service_account_json",
    "gemini_api_key",
    "naver_client_secret",
})

_SCHEDULE_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# GET 응답의 기본값 — DB에 키가 없을 때 이 값으로 채움
_DEFAULTS: dict[str, str] = {
    "schedule_time": "08:00",
    "news_provider": "serpapi",
    "serpapi_key": "",
    "naver_client_id": "",
    "naver_client_secret": "",
    "ai_provider": "openai",
    "openai_key": "",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.0-flash-preview-04-17",
    "resend_key": "",
    "recipient_emails": "",
    "google_sheet_id": "",
    "google_service_account_json": "",
}


class SettingsPayload(BaseModel):
    schedule_time: str = "08:00"
    # 뉴스 수집
    news_provider: str = "serpapi"
    serpapi_key: str | None = None
    naver_client_id: str = ""
    naver_client_secret: str | None = None
    # AI 요약
    ai_provider: str = "openai"
    openai_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash-preview-04-17"
    # 이메일
    resend_key: str | None = None
    recipient_emails: str = ""
    # Google Sheets
    google_sheet_id: str = ""
    google_service_account_json: str | None = None

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

    # DB에 저장된 값으로 덮어쓰기, 없는 키는 기본값 사용
    db_map: dict[str, str] = {r.key: r.value for r in rows}
    merged = {**_DEFAULTS, **db_map}

    return {
        key: ("***" if key in SECRET_KEYS and value else value)
        for key, value in merged.items()
    }


@router.post("")
async def save_settings(body: SettingsPayload, db: AsyncSession = Depends(get_db)):
    # exclude_unset=True: 클라이언트가 명시적으로 보낸 필드만 처리
    # (Pydantic default 값으로 자동 채워진 필드는 DB에 강제 저장하지 않음)
    payload = body.model_dump(exclude_unset=True)
    for key, value in payload.items():
        # None이면 기존 값 유지 (시크릿 키 미변경 처리)
        if value is None:
            continue
        result = await db.execute(select(Setting).where(Setting.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    await db.commit()

    if "schedule_time" in payload and payload["schedule_time"] is not None:
        from services.scheduler import setup_scheduler
        setup_scheduler(payload["schedule_time"])

    return {"status": "success"}
