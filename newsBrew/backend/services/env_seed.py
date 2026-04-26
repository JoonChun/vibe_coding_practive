import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Setting

logger = logging.getLogger(__name__)

_ENV_TO_DB: dict[str, str] = {
    "NAVER_CLIENT_ID": "naver_client_id",
    "NAVER_CLIENT_SECRET": "naver_client_secret",
    "GOOGLE_SHEET_ID": "google_sheet_id",
    "RESEND_API_KEY": "resend_key",
    "EMAIL_TO": "recipient_emails",
    "GEMINI_API_KEY": "gemini_api_key",
    "GEMINI_MODEL": "gemini_model",
    "OPENAI_API_KEY": "openai_key",
    "SERPAPI_KEY": "serpapi_key",
}


def _read_service_account_json() -> str | None:
    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "").strip()
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON_PATH 파일을 찾을 수 없음: %s", path)
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("service account JSON 읽기 실패: %s", e)
        return None


def _infer_providers(present_env: dict[str, str]) -> dict[str, str]:
    inferred: dict[str, str] = {}
    if present_env.get("NAVER_CLIENT_ID") and present_env.get("NAVER_CLIENT_SECRET"):
        inferred["news_provider"] = "naver"
    elif present_env.get("SERPAPI_KEY"):
        inferred["news_provider"] = "serpapi"
    if present_env.get("GEMINI_API_KEY"):
        inferred["ai_provider"] = "gemini"
    elif present_env.get("OPENAI_API_KEY"):
        inferred["ai_provider"] = "openai"
    return inferred


async def seed_settings_from_env(db: AsyncSession) -> int:
    """.env 값으로 DB Setting 테이블을 시드. DB에 이미 키가 있으면 건너뜀."""
    present: dict[str, str] = {}
    for env_key in _ENV_TO_DB:
        val = os.getenv(env_key, "").strip()
        if val:
            present[env_key] = val

    candidates: dict[str, str] = {
        _ENV_TO_DB[env_key]: val for env_key, val in present.items()
    }
    candidates.update(_infer_providers(present))

    sa_json = _read_service_account_json()
    if sa_json:
        candidates["google_service_account_json"] = sa_json

    if not candidates:
        return 0

    result = await db.execute(
        select(Setting.key).where(Setting.key.in_(candidates.keys()))
    )
    existing_keys = set(result.scalars().all())

    seeded = 0
    for key, value in candidates.items():
        if key in existing_keys:
            continue
        db.add(Setting(key=key, value=value))
        seeded += 1

    if seeded > 0:
        await db.commit()
        logger.info(".env에서 %d개 설정을 DB에 시드", seeded)

    return seeded
