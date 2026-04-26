import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from main import app
from database.database import get_db
from tests.conftest import db_session  # noqa

@pytest.fixture
def override_db(db_session):
    async def _get_db_override():
        yield db_session
    app.dependency_overrides[get_db] = _get_db_override
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_brew_start_returns_started(override_db, db_session):
    from database.models import Keyword, Setting
    db_session.add(Keyword(word="AI", exclude_words=""))
    db_session.add(Setting(key="serpapi_key", value="test"))
    db_session.add(Setting(key="openai_key", value="test"))
    db_session.add(Setting(key="resend_key", value="test"))
    db_session.add(Setting(key="recipient_emails", value="test@example.com"))
    db_session.add(Setting(key="google_sheet_id", value=""))
    db_session.add(Setting(key="google_service_account_json", value=""))
    await db_session.commit()

    with patch("services.brew_orchestrator.run_brew_pipeline", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/brew/start")

    assert resp.status_code == 200
    assert resp.json()["status"] == "started"
