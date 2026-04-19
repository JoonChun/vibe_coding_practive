from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.database import get_db
from database.models import Archive

router = APIRouter(prefix="/api/archives", tags=["archives"])

@router.get("")
async def list_archives(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Archive.date, func.count(Archive.id).label("summary_count"))
        .group_by(Archive.date)
        .order_by(Archive.date.desc())
    )
    return [{"date": row.date, "summary_count": row.summary_count} for row in result.all()]

@router.get("/{date}")
async def get_archive_by_date(date: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Archive)
        .where(Archive.date == date)
        .order_by(Archive.importance_score.desc())
    )
    items = result.scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No archives found for this date")
    return [
        {
            "id": a.id, "keyword": a.keyword, "title": a.title,
            "url": a.url, "source": a.source, "published_at": a.published_at,
            "summary": a.summary, "importance_score": a.importance_score
        }
        for a in items
    ]
