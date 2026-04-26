from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False, unique=True)
    exclude_words = Column(String(500), default="")
    max_results = Column(Integer, default=15)
    time_range_hours = Column(Integer, default=24)
    is_active = Column(Integer, default=1)  # 1=활성, 0=비활성
    created_at = Column(DateTime, default=datetime.utcnow)

class Archive(Base):
    __tablename__ = "archives"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), nullable=False)
    keyword = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    source = Column(String(200))
    published_at = Column(String(50))
    summary = Column(Text)
    importance_score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=False)
