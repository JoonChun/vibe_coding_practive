import pytest
from httpx import AsyncClient, ASGITransport
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
async def test_save_and_get_settings(override_db):
    payload = {
        "schedule_time": "08:00",
        "serpapi_key": "test_key",
        "openai_key": "test_openai",
        "resend_key": "test_resend",
        "recipient_emails": "test@example.com",
        "google_sheet_id": "sheet123",
        "google_service_account_json": ""
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        save_resp = await client.post("/api/settings", json=payload)
        assert save_resp.status_code == 200
        get_resp = await client.get("/api/settings")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["schedule_time"] == "08:00"
    assert data["recipient_emails"] == "test@example.com"

@pytest.mark.asyncio
async def test_get_settings_empty(override_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/settings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
