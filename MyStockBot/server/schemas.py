from pydantic import BaseModel


class WatchlistItemIn(BaseModel):
    code: str
    name: str


class WatchlistItemOut(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    created_at: str
    market: str | None = None


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItemOut]


class FactorDetail(BaseModel):
    macd_1d: str | None = None
    rsi_1d: str | None = None
    rsi_value_1d: float | None = None
    macd_60m: str | None = None
    rsi_60m: str | None = None
    rsi_value_60m: float | None = None
    bb_upper: float | None = None
    bb_mid: float | None = None
    bb_lower: float | None = None
    per: float | None = None
    pbr: float | None = None
    roe: float | None = None
    short_score: int | None = None
    long_score: int | None = None


class SnapshotItem(BaseModel):
    code: str
    name: str
    close: float | None = None
    short_view: str | None = None
    long_view: str | None = None
    source: str | None = None
    error: str | None = None
    change: float | None = None
    change_pct: float | None = None
    factors: FactorDetail | None = None


class SnapshotResponse(BaseModel):
    generated_at: str
    cache_hit: bool
    items: list[SnapshotItem]


class IndexItem(BaseModel):
    code: str  # "KOSPI" | "KOSDAQ"
    name: str
    value: float | None = None      # 현재 지수
    change: float | None = None     # 전일 대비 등락폭
    change_pct: float | None = None # 등락률 %
    source: str | None = None       # "yfinance" | None(조회 실패)
    error: str | None = None


class IndicesResponse(BaseModel):
    generated_at: str
    cache_hit: bool
    items: list[IndexItem]


class SearchItem(BaseModel):
    code: str
    name: str
    market: str


class SearchResponse(BaseModel):
    items: list[SearchItem]


class CandleItem(BaseModel):
    t: int  # Unix epoch 초(UTC). 일봉+ 는 KST 자정 기준, 분봉은 실제 캔들 시각.
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class CandlesResponse(BaseModel):
    code: str
    tf: str
    source: str | None = None  # "kis" | "yfinance" | None(데이터 없음/수집 실패)
    items: list[CandleItem]
