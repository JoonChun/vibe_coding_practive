from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./newsbrew.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    from database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 기존 DB에 새 컬럼 추가 (이미 있으면 무시)
        for ddl in [
            "ALTER TABLE keywords ADD COLUMN max_results INTEGER DEFAULT 15",
            "ALTER TABLE keywords ADD COLUMN is_active INTEGER DEFAULT 1",
            "ALTER TABLE keywords ADD COLUMN time_range_hours INTEGER DEFAULT 24",
        ]:
            try:
                await conn.execute(__import__('sqlalchemy').text(ddl))
            except Exception:
                pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
