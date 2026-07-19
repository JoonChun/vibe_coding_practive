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


class PullbackCheck(BaseModel):
    """눌림목 체크리스트 항목 1개(프론트 렌더 계약 — label 문자열·순서 고정,
    src/indicators.py pullback_signal 의 checks 리스트를 그대로 옮겨 담는다)."""
    label: str
    ok: bool


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
    pullback_status: str | None = None
    pullback_reason: str | None = None
    pullback_trend_up: bool | None = None
    pullback_checks: list[PullbackCheck] | None = None


class LiveJudgment(BaseModel):
    """tick_aggregator.py 가 5초 주기로 재계산하는 실시간 참고 판정(참고용, 확정 아님).
    계산 불가한 항목은 None, 장외에는 마지막 값이 그대로 유지된다(freeze)."""
    short_view_live: str | None = None
    short_score_live: int | None = None
    long_view_live: str | None = None
    long_score_live: int | None = None
    updated_at: str | None = None


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
    live: LiveJudgment | None = None


class SnapshotResponse(BaseModel):
    generated_at: str
    cache_hit: bool
    items: list[SnapshotItem]


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


class WhatIfSide(BaseModel):
    """가격 비율 기준 손익 결과(종목·코스피 병치 공통 산식). 배당/분할/수수료 미반영."""
    buy_price: float
    current_price: float
    eval_amount: float
    profit: float
    return_pct: float
    multiple: float


class WhatIfBotJudgment(BaseModel):
    """매수일(buy_date) 시점까지의 데이터만으로 재현한 '그날의 봇 판정'(참고용).
    재무비율(PER/PBR/ROE)은 과거 재현이 불가능해 항상 제외한다(note 고정 문구)."""
    long_view: str | None = None
    macd_1d: str | None = None
    rsi_1d: str | None = None
    pullback_status: str | None = None
    note: str


class WhatIfResponse(BaseModel):
    code: str
    requested_date: str
    buy_date: str | None = None
    buy_price: float | None = None
    amount: int
    shares: float | None = None
    current_date: str | None = None
    current_price: float | None = None
    eval_amount: float | None = None
    profit: float | None = None
    return_pct: float | None = None
    multiple: float | None = None
    kospi: WhatIfSide | None = None
    bot_judgment: WhatIfBotJudgment | None = None
    source: str | None = None  # 종목 일봉 소스("kis"|"yfinance"|None)
    error: str | None = None
