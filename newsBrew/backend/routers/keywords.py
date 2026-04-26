from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from database.database import get_db
from database.models import Keyword

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


class KeywordCreate(BaseModel):
    word: str
    exclude_words: str = ""

    @field_validator("word")
    @classmethod
    def word_must_not_be_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("word must not be blank")
        return v

    @field_validator("exclude_words")
    @classmethod
    def exclude_words_none_to_empty(cls, v: Optional[str]) -> str:
        return v if v is not None else ""


class KeywordUpdate(BaseModel):
    word: Optional[str] = None
    exclude_words: Optional[str] = None
    max_results: Optional[int] = None
    time_range_hours: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("word")
    @classmethod
    def word_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("word must not be blank")
        return v


class KeywordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    word: str
    exclude_words: str
    max_results: int = 15
    time_range_hours: int = 24
    is_active: bool = True
    created_at: datetime | None = None


@router.get("", response_model=list[KeywordResponse])
async def list_keywords(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).order_by(Keyword.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=KeywordResponse, status_code=201)
async def create_keyword(body: KeywordCreate, db: AsyncSession = Depends(get_db)):
    kw = Keyword(word=body.word, exclude_words=body.exclude_words)
    db.add(kw)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Keyword '{body.word}' already exists")
    await db.refresh(kw)
    return kw


@router.patch("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(keyword_id: int, body: KeywordUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    if body.word is not None:
        kw.word = body.word
    if body.exclude_words is not None:
        kw.exclude_words = body.exclude_words
    if body.max_results is not None:
        kw.max_results = body.max_results
    if body.time_range_hours is not None:
        kw.time_range_hours = body.time_range_hours
    if body.is_active is not None:
        kw.is_active = 1 if body.is_active else 0

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Keyword '{body.word}' already exists")
    await db.refresh(kw)
    return kw


@router.delete("/{keyword_id}")
async def delete_keyword(keyword_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(kw)
    await db.commit()
    return {"status": "success"}
