import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import get_db
from database.models import Archive
from tests.conftest import db_session  # noqa

@pytest.fixture
def override_db(db_session):
    async def _get_db_override():
        yield db_session
    app.dependency_overrides[get_db] = _get_db_override
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_list_archives_empty(override_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/archives")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_list_archives_groups_by_date(override_db, db_session):
    db_session.add(Archive(date="2026-04-19", keyword="AI", title="뉴스1",
                           url="http://a.com", summary="요약1", importance_score=8))
    db_session.add(Archive(date="2026-04-19", keyword="반도체", title="뉴스2",
                           url="http://b.com", summary="요약2", importance_score=7))
    db_session.add(Archive(date="2026-04-18", keyword="AI", title="뉴스3",
                           url="http://c.com", summary="요약3", importance_score=6))
    await db_session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/archives")
    data = resp.json()
    assert len(data) == 2
    assert data[0]["date"] == "2026-04-19"
    assert data[0]["summary_count"] == 2

@pytest.mark.asyncio
async def test_get_archive_detail(override_db, db_session):
    db_session.add(Archive(date="2026-04-19", keyword="AI", title="상세뉴스",
                           url="http://detail.com", summary="상세요약", importance_score=9))
    await db_session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/archives/2026-04-19")
    assert resp.status_code == 200
    items = resp.json()
    assert any(a["title"] == "상세뉴스" for a in items)
