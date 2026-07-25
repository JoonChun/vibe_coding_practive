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


class WatchlistSyncResponse(BaseModel):
    """POST /api/watchlist/sync — 시트 Dashboard → 앱 임포트 결과."""
    enabled: bool       # 자격증명·SPREADSHEET_ID 가 있어 동기화가 동작하는지
    sheet_items: int    # 시트에서 읽은 수집 대상 종목 수('해제' 제외)
    added: int          # 앱에 새로 추가된 종목 수
    skipped: int        # 앱에 이미 있어 건너뛴 종목 수
    failed: int         # 추가 실패 건수


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
    priced_incomplete: bool = False  # 일부 보유의 현재가 부재 → 평가금액은 장부가로 대체됨
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


class BacktestSide(BaseModel):
    signals: int
    effective_signals: int = 0          # 겹치는 선행구간을 보정한 독립 표본 근사(signals//horizon)
    hit_rate: float | None = None       # 매수: 상승 비율 / 매도: 하락 비율 (%)
    hit_rate_ci: list[float] | None = None  # 적중률 95% 신뢰구간 [하한%, 상한%] (보정 표본 기준)
    avg_forward_pct: float | None = None  # 판정 후 N일 평균 수익률 %
    low_confidence: bool = False        # 보정 표본이 너무 적어 적중률을 신뢰할 수 없음


class BacktestPoint(BaseModel):
    t: int
    strategy: float   # 판정 따라가기 누적수익률 %
    buyhold: float    # 단순 보유 누적수익률 %


class BacktestResponse(BaseModel):
    code: str
    horizon_days: int
    evaluated_days: int
    start_date: str | None = None
    end_date: str | None = None
    bars_used: int = 0             # 실제 계산에 쓴 일봉 수
    bars_available: int = 0        # 보유 이력 전체 일봉 수(캡 적용 전)
    max_bars: int = 0              # 계산 비용 상한(이보다 길면 최근분만 사용)
    truncated: bool = False        # 위 상한으로 이력이 잘렸는지
    fundamentals_included: bool = False  # 재무지표 반영 여부(현재 기술적 판정만 → 항상 False)
    buy: BacktestSide
    sell: BacktestSide
    strategy_return_pct: float
    buy_hold_return_pct: float
    notes: list[str] = []          # 가정·한계·잘림 경고
    curve: list[BacktestPoint]


class DcaPoint(BaseModel):
    t: int
    principal: float  # 누적 투자원금
    value: float      # 그 시점 평가금액


class DcaResponse(BaseModel):
    code: str
    mode: str          # "qty" | "amount"
    per: float         # 회당 매수 주수 또는 금액
    buys: int          # 매수 횟수
    total_shares: float
    avg_price: float | None = None
    current_price: float
    principal: float   # 총 투자원금
    eval_value: float  # 현재 평가금액
    profit: float
    return_pct: float
    freq: str = "monthly"       # "weekly" | "monthly" | "quarterly"
    reinvest: bool = False      # 배당 재투자 실제 반영 여부(현재 미지원 → 항상 False)
    notes: list[str] = []       # 가정·한계·잘림 경고
    start_date: str | None = None
    end_date: str | None = None
    source: str | None = None
    curve: list[DcaPoint]


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
