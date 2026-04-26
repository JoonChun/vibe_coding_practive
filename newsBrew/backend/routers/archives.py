from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from pydantic import BaseModel
from database.database import get_db
from database.models import Archive

router = APIRouter(prefix="/api/archives", tags=["archives"])


# --------------------------------------------------------------------------- #
#  Response Schemas                                                             #
# --------------------------------------------------------------------------- #

class ArchiveItem(BaseModel):
    id: int
    date: str
    keyword: str
    title: str
    url: str
    source: Optional[str] = None
    published_at: Optional[str] = None
    summary: Optional[str] = None
    importance_score: int = 0

    model_config = {"from_attributes": True}


class ArchiveDateSummary(BaseModel):
    date: str
    summary_count: int


class ArchiveListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[ArchiveItem]


# --------------------------------------------------------------------------- #
#  GET /api/archives  —  날짜별 요약 목록 또는 상세 목록 (쿼리 파라미터)          #
# --------------------------------------------------------------------------- #

@router.get("", response_model=ArchiveListResponse)
async def list_archives(
    date: Optional[str] = Query(None, description="필터링 날짜 (YYYY-MM-DD)"),
    keyword: Optional[str] = Query(None, description="키워드 검색 (부분 일치)"),
    page: int = Query(1, ge=1, description="페이지 번호 (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="페이지 당 항목 수"),
    db: AsyncSession = Depends(get_db),
):
    """
    Archive 목록을 반환합니다.
    - date, keyword 파라미터로 필터링 가능
    - 정렬: date DESC, importance_score DESC
    - 페이지네이션: page / size
    """
    query = select(Archive)

    if date:
        query = query.where(Archive.date == date)
    if keyword:
        query = query.where(Archive.keyword.ilike(f"%{keyword}%"))

    # 전체 카운트
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # 정렬 + 페이지네이션
    offset = (page - 1) * size
    query = (
        query
        .order_by(Archive.date.desc(), Archive.importance_score.desc())
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(query)
    items = result.scalars().all()

    return ArchiveListResponse(
        total=total,
        page=page,
        size=size,
        items=[ArchiveItem.model_validate(a) for a in items],
    )


# --------------------------------------------------------------------------- #
#  GET /api/archives/dates  —  날짜별 요약 카운트 목록                           #
# --------------------------------------------------------------------------- #

@router.get("/dates", response_model=list[ArchiveDateSummary])
async def list_archive_dates(db: AsyncSession = Depends(get_db)):
    """
    브루잉 기록이 있는 날짜 목록과 각 날짜의 기사 수를 반환합니다.
    날짜 내림차순 정렬.
    """
    result = await db.execute(
        select(Archive.date, func.count(Archive.id).label("summary_count"))
        .group_by(Archive.date)
        .order_by(Archive.date.desc())
    )
    return [
        ArchiveDateSummary(date=row.date, summary_count=row.summary_count)
        for row in result.all()
    ]


# --------------------------------------------------------------------------- #
#  GET /api/archives/{date}  —  특정 날짜 상세 (keyword 필터 선택)               #
# --------------------------------------------------------------------------- #

@router.get("/{date}", response_model=list[ArchiveItem])
async def get_archive_by_date(
    date: str,
    keyword: Optional[str] = Query(None, description="키워드 필터 (완전 일치)"),
    db: AsyncSession = Depends(get_db),
):
    """
    특정 날짜의 Archive 목록을 반환합니다.
    - keyword 파라미터로 특정 키워드만 필터 가능
    - 정렬: importance_score DESC
    """
    query = select(Archive).where(Archive.date == date)

    if keyword:
        query = query.where(Archive.keyword == keyword)

    query = query.order_by(Archive.importance_score.desc())

    result = await db.execute(query)
    items = result.scalars().all()

    if not items:
        raise HTTPException(status_code=404, detail="No archives found for this date")

    return [ArchiveItem.model_validate(a) for a in items]
