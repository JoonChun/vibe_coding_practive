import pytest
from sqlalchemy import select
from database.models import Keyword, Archive, Setting

@pytest.mark.asyncio
async def test_keyword_model(db_session):
    kw = Keyword(word="AI", exclude_words="광고,홍보")
    db_session.add(kw)
    await db_session.commit()
    result = await db_session.execute(select(Keyword).where(Keyword.word == "AI"))
    found = result.scalar_one()
    assert found.word == "AI"
    assert found.exclude_words == "광고,홍보"
    assert found.id is not None

@pytest.mark.asyncio
async def test_setting_model(db_session):
    s = Setting(key="schedule_time", value="08:00")
    db_session.add(s)
    await db_session.commit()
    result = await db_session.execute(select(Setting).where(Setting.key == "schedule_time"))
    found = result.scalar_one()
    assert found.value == "08:00"

@pytest.mark.asyncio
async def test_archive_model(db_session):
    a = Archive(
        date="2026-04-19", keyword="AI", title="테스트 뉴스",
        url="http://test.com", source="테스트", summary="요약", importance_score=8
    )
    db_session.add(a)
    await db_session.commit()
    result = await db_session.execute(select(Archive).where(Archive.date == "2026-04-19"))
    found = result.scalar_one()
    assert found.title == "테스트 뉴스"
    assert found.importance_score == 8
