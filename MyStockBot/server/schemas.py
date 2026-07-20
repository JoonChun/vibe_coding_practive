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


class PaperHolding(BaseModel):
    code: str
    name: str
    qty: int
    avg_cost: float
    price: float | None = None        # 현재가(스냅샷)
    eval_amount: float | None = None  # 평가금액 = price * qty
    pnl: float | None = None          # 평가손익
    pnl_pct: float | None = None      # 수익률 %


class PaperAccountResponse(BaseModel):
    cash: float                # 현금 잔액
    seed: float                # 초기 시드머니
    holdings_value: float      # 주식 평가금액 합
    total_value: float         # 총 평가자산 = cash + holdings_value
    total_pnl: float           # 총 평가손익 = total_value - seed
    total_pnl_pct: float
    holdings: list[PaperHolding]


class PaperTrade(BaseModel):
    id: int
    ts: str
    code: str
    name: str
    side: str  # "buy" | "sell"
    qty: int
    price: float
    amount: float


class PaperTradesResponse(BaseModel):
    items: list[PaperTrade]


class PaperOrderRequest(BaseModel):
    code: str
    side: str  # "buy" | "sell"
    qty: int


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
