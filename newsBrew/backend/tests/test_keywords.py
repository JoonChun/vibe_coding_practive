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
async def test_create_keyword(override_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/keywords", json={"word": "인공지능", "exclude_words": "광고"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["word"] == "인공지능"
    assert data["id"] is not None

@pytest.mark.asyncio
async def test_list_keywords(override_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/keywords", json={"word": "반도체", "exclude_words": ""})
        resp = await client.get("/api/keywords")
    assert resp.status_code == 200
    assert any(k["word"] == "반도체" for k in resp.json())

@pytest.mark.asyncio
async def test_delete_keyword(override_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/keywords", json={"word": "삭제테스트", "exclude_words": ""})
        kw_id = create_resp.json()["id"]
        del_resp = await client.delete(f"/api/keywords/{kw_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

@pytest.mark.asyncio
async def test_delete_nonexistent_keyword(override_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/keywords/99999")
    assert resp.status_code == 404
