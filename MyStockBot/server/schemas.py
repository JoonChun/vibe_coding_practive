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


class FactorRow(BaseModel):
    """판정 기여요인 1행 — 백엔드가 계산해 내려주고 화면은 그리기만 한다."""
    key: str            # "macd" | "rsi" | "per" | "pbr" | "roe"
    label: str          # 표시 문구 (예: "MACD 골든크로스(진입)", "RSI 중립 · RSI 52.4")
    score: int          # 이 팩터의 기여 점수
    max_abs: int        # 기여 바 폭 계산용 — 이 팩터가 가질 수 있는 점수 절대값 최댓값
    rule: str           # 이 점수가 나온 이유 (예: "골든크로스 — 강한 진입 (+2)")


class DecisionRules(BaseModel):
    """판정 임계값 — 화면이 규칙을 하드코딩하지 않도록 응답에 함께 싣는다."""
    weak: int                                 # |합계| 이상이면 매수/매도
    short_strong: int                         # 단기 강력 등급 경계
    long_strong: int                          # 장기 강력 등급 경계
    long_strong_requires_tech_confirm: bool   # 장기 강력 등급에 기술 지표 확증을 요구하는지


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
    breakdown_short: list[FactorRow] = []   # 단기(60분봉) 기여요인 — MACD·RSI
    breakdown_long: list[FactorRow] = []    # 장기(일봉+재무) 기여요인 — MACD·RSI·PER·PBR·ROE


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
    rules: DecisionRules | None = None  # 판정 임계값(화면 캡션·게이지 정규화에 사용)


class MarketBreadth(BaseModel):
    """시장 폭(등락종목수) — KIS 국내업종 현재지수(FHPUP02100000) 경로에서만 제공된다."""
    up: int          # 상승 종목 수
    flat: int        # 보합 종목 수
    down: int        # 하락 종목 수
    limit_up: int    # 상한 종목 수
    limit_down: int  # 하한 종목 수


class IndexItem(BaseModel):
    code: str  # "KOSPI" | "KOSDAQ"
    name: str
    value: float | None = None      # 현재 지수
    change: float | None = None     # 전일 대비 등락폭
    change_pct: float | None = None # 등락률 %
    # 시장 폭. 일자별 지수·yfinance 폴백 경로에는 없으므로 None 일 수 있다.
    breadth: MarketBreadth | None = None
    source: str | None = None       # "kis" | "yfinance" | None(조회 실패)
    error: str | None = None
    # 이번 조회는 실패했지만 직전 성공 값을 대신 실어 보낸 경우 True.
    # 이때 value 는 있고 error 도 함께 있다 — 화면은 "값 + 낡음 표시"로 그려야 하고,
    # error 가 있다는 이유만으로 "데이터 없음"을 띄우면 멀쩡한 값을 버리게 된다.
    stale: bool = False
    stale_age_seconds: float | None = None  # 그 값을 받은 뒤 지난 시간(초)


class MarketStatusResponse(BaseModel):
    """GET /api/market/status — 장 운영 상태와 세션 경계."""
    status: str          # "pre" | "open" | "closed" | "holiday"
    label: str           # 화면 표시 라벨("장전"/"장중"/"장마감"/"휴장")
    server_time: str     # ISO8601 (Asia/Seoul)
    session_open: str    # 의미 있는 다음 세션의 개장 시각 — 프론트 카운트다운 기준
    session_close: str   # 같은 세션의 마감 시각
    session_date: str    # 그 세션의 날짜(YYYY-MM-DD)
    reference_trading_day: str  # 지금 보이는 시세가 속한 거래일(휴장·장전이면 직전 거래일)
    calendar_covered: bool      # 이 날짜의 판정을 신뢰할 수 있는지(False 면 음력 연휴 누락 가능)
    calendar_source: str = "builtin"  # "kis"(공식 휴장일 캐시) | "builtin"(하드코딩 표)


class AlertConfigResponse(BaseModel):
    """GET /api/alerts/config — 알림 설정 진단.

    ★ 웹훅 URL·메일 주소 같은 비밀은 절대 담지 않는다. 설정 여부(bool)만 노출한다.
    """
    enabled: bool                  # DECISION_ALERT_ENABLED
    channels: list[str]            # 설정된 채널 이름("slack" | "email")
    views: list[str]               # 감시 중인 판정 종류("short" | "long")
    side_only: bool                # 측(매수/관망/매도)이 바뀔 때만 알리는지
    confirm_cycles: int            # 확정에 필요한 연속 사이클 수
    cooldown_minutes: int          # 같은 종목·종류의 최소 알림 간격
    in_window: bool                # 지금이 알림 시간대(거래일 정규장)인지
    baselines: int                 # 저장된 기준선 행 수


class AlertBaseline(BaseModel):
    code: str
    view_kind: str      # "short" | "long"
    view: str           # 마지막 기준 판정
    source: str | None = None
    notified_at: str | None = None  # 실제 발송 시각(UTC). 무음 시딩만 됐으면 None
    updated_at: str | None = None


class AlertStateResponse(BaseModel):
    items: list[AlertBaseline]


class AlertHistoryItem(BaseModel):
    """GET /api/alerts/history 항목 — **실제로 알림으로 나간** 전환 1건.

    기준선(AlertBaseline)과 역할이 다르다: 기준선은 종목·종류당 한 행만 남는 캐시고,
    이력은 append-only 기록이라 "언제 어떻게 바뀌었나"에 답한다. 쿨다운·히스테리시스로
    눌린 전환은 들어오지 않는다(유실이 아니라 지연이므로 나중에 발화하며 그때 기록된다).
    """
    id: int
    notified_at: str
    code: str
    name: str
    view_kind: str          # "short" | "long"
    before_view: str
    after_view: str
    close: float | None = None
    change_pct: float | None = None
    channels: str           # 발송에 **성공한** 채널만 콤마로 이은 값


class AlertHistoryResponse(BaseModel):
    items: list[AlertHistoryItem]


class AlertTestResponse(BaseModel):
    """POST /api/alerts/test — 채널별 발송 결과.

    이 저장소는 Slack 도메인이 막힌 환경에서 개발되어 **실제 발송이 검증되지 않았다.**
    사용자가 자기 네트워크에서 이 엔드포인트로 한 번 확인하는 것이 유일한 검증 경로다.
    """
    channels: list[str]         # 설정된 채널
    results: dict[str, bool]    # 채널별 성공 여부
    # 실패한 채널의 사유(성공한 채널은 없음). **비밀은 지운 상태로만 담긴다** —
    # 웹훅 URL 과 Gmail 앱 비밀번호는 그 자체가 자격증명이라 응답에 실리면 안 된다
    # (alert_channels.scrub / notifier.send_html 참고). 사유를 응답에 넣는 이유는
    # 이 엔드포인트가 진단 도구인데 bool 만 주면 사용자가 로그를 찾아 헤매기 때문이다.
    reasons: dict[str, str] = {}
    detail: str


class IndicesResponse(BaseModel):
    generated_at: str
    # "이번 요청에서 외부 조회를 한 번도 하지 않았다". 항목별 갱신 시점이 다를 수 있으므로
    # 개별 낡음은 IndexItem.stale / stale_age_seconds 로 읽는다.
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
    # 총손익의 분해. 수수료·세금이 없으므로 realized + unrealized == total_pnl 이다
    # (realized_unknown_trades 가 0 인 경우).
    realized_pnl: float = 0.0    # 매도로 확정된 손익 누적
    unrealized_pnl: float = 0.0  # 보유 평가금액 - 보유 원가
    # 실현손익이 기록되기 전(마이그레이션 이전)의 매도 건수. 0 이 아니면 위 분해가
    # 총손익과 맞지 않는다 — 숫자를 억지로 맞추지 않고 그 사실을 노출한다.
    realized_unknown_trades: int = 0
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
    # 체결가 출처. "market" = 수집된 시세, "book" = 장부가(평균단가) 대체 체결.
    # None = 이 기록이 도입되기 전의 거래(모른다 — 'market' 으로 채우지 않는다).
    price_source: str | None = None
    # 체결 시점의 장 상태("open"/"pre"/"closed"/"holiday"). None = 기록 전 거래.
    market_status: str | None = None
    # 매도에서 확정된 실현손익. 매수는 None, 기록 전 매도도 None.
    realized_pnl: float | None = None


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
