// 백엔드 API 스키마와 1:1 대응 (MyStockBot/server/schemas.py 참조)

export type SignalView =
  | "강력매수"
  | "매수"
  | "관망"
  | "매도"
  | "강력매도"
  | "데이터부족";

/** 판정 분포 스트립 등에서 사용 — "데이터부족"을 제외한 5단계 판정 */
export type DecisionView = Exclude<SignalView, "데이터부족">;

export type SnapshotSource = "kis" | "yfinance";

/** stock_master.market — 코스피/코스닥 구분 */
export type MarketType = "KOSPI" | "KOSDAQ";

export interface WatchlistItem {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  market?: string | null;
}

export interface WatchlistListResponse {
  items: WatchlistItem[];
}

export interface WatchlistItemInput {
  code: string;
  name: string;
}

/** GET /api/indices 결과 항목 — 코스피/코스닥 지수 카드용 */
/** 시장 폭(등락종목수) — KIS 현재지수 경로에서만 제공. 폴백 경로에서는 null. */
export interface MarketBreadth {
  up: number;
  flat: number;
  down: number;
  limit_up: number;
  limit_down: number;
}

export interface IndexItem {
  code: string; // "KOSPI" | "KOSDAQ"
  name: string;
  value: number | null;
  change: number | null;
  change_pct: number | null;
  /** 시장 폭. KIS 현재지수 경로에서만 오고, 폴백 경로에서는 null */
  breadth: MarketBreadth | null;
  source: SnapshotSource | null;
  error: string | null;
  /**
   * 이번 조회는 실패했지만 직전 성공 값을 대신 받은 경우 true.
   * 이때 value 가 있고 error 도 함께 온다 — error 만 보고 "데이터 없음"을 띄우면
   * 멀쩡한 값을 버린다. 값을 그리고 낡음만 표시해야 한다.
   */
  stale: boolean;
  /** 그 값을 받은 뒤 지난 시간(초). stale 이 아니면 null */
  stale_age_seconds: number | null;
}

/** 장 운영 상태 (GET /api/market/status) */
export type MarketStatusCode = "pre" | "open" | "closed" | "holiday";

export interface MarketStatus {
  status: MarketStatusCode;
  /** 화면 표시 라벨 — 서버가 내려준다(프론트가 문자열을 복제하지 않도록) */
  label: string;
  server_time: string;
  /** 의미 있는 다음 세션의 개장/마감 — 카운트다운은 이 값으로 로컬 계산한다 */
  session_open: string;
  session_close: string;
  session_date: string;
  /** 지금 보이는 시세가 속한 거래일. 휴장·장전이면 직전 거래일 */
  reference_trading_day: string;
  /** 이 날짜의 판정을 신뢰할 수 있는지. false 면 음력 연휴를 놓칠 수 있다 */
  calendar_covered: boolean;
  /** 판정 근거 — "kis"(공식 휴장일 캐시) | "builtin"(하드코딩 표) */
  calendar_source: "kis" | "builtin";
}

export interface IndicesResponse {
  generated_at: string;
  cache_hit: boolean;
  items: IndexItem[];
}

/** 판정 백테스트 (GET /api/stocks/{code}/backtest) */
export interface BacktestSide {
  signals: number;
  /** 겹치는 선행구간을 보정한 독립 표본 근사(signals // horizon) */
  effective_signals: number;
  hit_rate: number | null;
  /** 적중률 95% 신뢰구간 [하한%, 상한%] — 보정 표본 기준 */
  hit_rate_ci: [number, number] | null;
  avg_forward_pct: number | null;
  /** 보정 표본이 너무 적어 적중률을 신뢰할 수 없음 */
  low_confidence: boolean;
}

export interface BacktestPoint {
  t: number;
  strategy: number;
  buyhold: number;
}

export interface BacktestResponse {
  code: string;
  horizon_days: number;
  evaluated_days: number;
  start_date: string | null;
  end_date: string | null;
  /** 실제 계산에 쓴 일봉 수 */
  bars_used: number;
  /** 보유 이력 전체 일봉 수(캡 적용 전) */
  bars_available: number;
  /** 계산 비용 상한 */
  max_bars: number;
  /** 위 상한으로 이력이 잘렸는지 */
  truncated: boolean;
  /** 재무지표 반영 여부(현재 기술적 판정만 → 항상 false) */
  fundamentals_included: boolean;
  buy: BacktestSide;
  sell: BacktestSide;
  strategy_return_pct: number;
  buy_hold_return_pct: number;
  /** 가정·한계·잘림 경고 */
  notes: string[];
  curve: BacktestPoint[];
}

/** 적립식 백테스트 (GET /api/stocks/{code}/dca) */
export interface DcaPoint {
  t: number;
  principal: number;
  value: number;
}

export interface DcaResponse {
  code: string;
  mode: "qty" | "amount";
  per: number;
  buys: number;
  total_shares: number;
  avg_price: number | null;
  current_price: number;
  principal: number;
  eval_value: number;
  profit: number;
  return_pct: number;
  freq: "weekly" | "monthly" | "quarterly";
  reinvest: boolean;
  notes: string[];
  start_date: string | null;
  end_date: string | null;
  source: SnapshotSource | null;
  curve: DcaPoint[];
}

/** 모의투자 보유 종목 (GET /api/paper/account) */
export interface PaperHolding {
  code: string;
  name: string;
  qty: number;
  avg_cost: number;
  price: number | null;
  eval_amount: number | null;
  pnl: number | null;
  pnl_pct: number | null;
}

export interface PaperAccount {
  cash: number;
  seed: number;
  holdings_value: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  /** 매도로 확정된 손익 누적 */
  realized_pnl: number;
  /** 보유 평가금액 - 보유 원가 */
  unrealized_pnl: number;
  /**
   * 실현손익이 기록되기 전의 매도 건수. 0 이 아니면
   * realized + unrealized 가 total_pnl 과 맞지 않는다.
   */
  realized_unknown_trades: number;
  holdings: PaperHolding[];
}

/** 체결가 출처. null = 이 기록이 도입되기 전의 거래(모름) */
export type PaperPriceSource = "market" | "book";

export interface PaperTrade {
  id: number;
  ts: string;
  code: string;
  name: string;
  side: "buy" | "sell";
  qty: number;
  price: number;
  amount: number;
  /** "market" = 수집된 시세 / "book" = 장부가(평균단가) 대체 체결 */
  price_source: PaperPriceSource | null;
  /** 체결 시점 장 상태 */
  market_status: MarketStatusCode | null;
  /** 매도에서 확정된 실현손익. 매수는 null */
  realized_pnl: number | null;
}

export interface PaperTradesResponse {
  items: PaperTrade[];
}

export interface PaperOrderInput {
  code: string;
  side: "buy" | "sell";
  qty: number;
}

/** GET /api/stocks/search 결과 항목 — 자동완성 드롭다운용 */
export interface SearchItem {
  code: string;
  name: string;
  market: MarketType;
}

export interface StockSearchResponse {
  items: SearchItem[];
}

/**
 * 판정 기여요인 1행 — **백엔드가 계산해 내려준다.**
 *
 * 예전에는 web/src/utils/factorScoring.ts 가 점수표·임계값·설명문을 TS 로 복제해 화면에서
 * 다시 계산했고, 그 파일 주석이 "백엔드 점수와 불일치할 수 있으므로 화면은 프론트 합계를
 * 우선한다"고 못박아 두어 화면 숫자와 실제 판정 근거가 갈라질 수 있었다. 지금은 계산 지점이
 * src/decision_rules.py + src/indicators.py 한 곳뿐이고 화면은 그리기만 한다.
 */
export interface FactorRow {
  key: "macd" | "rsi" | "per" | "pbr" | "roe";
  /** 표시 문구 — 예: "MACD 골든크로스(진입)", "RSI 중립 · RSI 52.4" */
  label: string;
  score: number;
  /** 기여 바 폭 계산용 — 이 팩터가 가질 수 있는 점수 절대값의 최댓값 */
  max_abs: number;
  /** 이 점수가 나온 이유 — 예: "골든크로스 — 강한 진입 (+2)" */
  rule: string;
}

/** 판정 임계값 — 화면이 규칙을 하드코딩하지 않도록 스냅샷 응답에 함께 실려 온다. */
export interface DecisionRules {
  /** |합계| 이상이면 매수/매도 */
  weak: number;
  /** 단기 강력 등급 경계 */
  short_strong: number;
  /** 장기 강력 등급 경계 */
  long_strong: number;
  /** 장기 강력 등급에 기술 지표의 같은 방향 확증을 요구하는지 */
  long_strong_requires_tech_confirm: boolean;
}

export interface SnapshotFactors {
  macd_1d: string | null;
  rsi_1d: string | null;
  rsi_value_1d: number | null;
  macd_60m: string | null;
  rsi_60m: string | null;
  rsi_value_60m: number | null;
  bb_upper: number | null;
  bb_mid: number | null;
  bb_lower: number | null;
  per: number | null;
  pbr: number | null;
  roe: number | null;
  /** 단기 스코어 합 — 임계값은 응답의 rules 참조 */
  short_score: number | null;
  /** 장기 스코어 합 — 임계값은 응답의 rules 참조 */
  long_score: number | null;
  /** 단기(60분봉) 기여요인 — MACD·RSI */
  breakdown_short: FactorRow[];
  /** 장기(일봉+재무) 기여요인 — MACD·RSI·PER·PBR·ROE */
  breakdown_long: FactorRow[];
}

export interface SnapshotItem {
  code: string;
  name: string;
  close: number | null;
  change: number | null; // 전일 대비 등락폭 (close - prev_close)
  change_pct: number | null; // 등락률 % (round 2)
  short_view: SignalView | null;
  long_view: SignalView | null;
  source: SnapshotSource | null;
  error: string | null;
  factors: SnapshotFactors | null;
}

export interface SnapshotResponse {
  generated_at: string;
  cache_hit: boolean;
  items: SnapshotItem[];
  /** 판정 임계값. 구버전 백엔드 호환을 위해 optional. */
  rules?: DecisionRules | null;
}


/** GET /api/stocks/{code}/candles 지원 주기 — 분봉 7종 + 일/주/월/년봉 */
export type Timeframe =
  | "1m"
  | "5m"
  | "15m"
  | "30m"
  | "60m"
  | "120m"
  | "240m"
  | "1d"
  | "1w"
  | "1M"
  | "1y";

/** 캔들 1개 — t는 Unix epoch 초(UTC). 일봉 이상은 KST 자정 기준 epoch.
 * open/high/low/close/volume은 백엔드가 결측 시 null을 반환할 수 있다(schemas.py CandleItem 참조). */
export interface CandleItem {
  t: number;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface CandlesResponse {
  code: string;
  tf: Timeframe;
  source: SnapshotSource | null;
  items: CandleItem[];
}

/** GET /api/alerts/config — 판정 전환 알림 설정(읽기 전용, .env 로 바꾼다) */
export interface AlertConfig {
  enabled: boolean;
  /** 실제로 인식된 채널. 값이 비어 있으면 설정이 안 됐거나 검증에서 거부됐다 */
  channels: string[];
  views: string[];
  side_only: boolean;
  confirm_cycles: number;
  cooldown_minutes: number;
  /** 지금이 알림 발송 시간대인가(장 시간 게이트) */
  in_window: boolean;
  /** 저장된 기준선 개수 = "마지막으로 알린 판정"을 아는 종목·종류 수 */
  baselines: number;
}

/** GET /api/alerts/state 항목 — 오알림 진단용 기준선 */
export interface AlertStateItem {
  code: string;
  view_kind: string;
  view: string;
  source: string | null;
  notified_at: string | null;
  updated_at: string;
}

export interface AlertStateResponse {
  items: AlertStateItem[];
}

/** POST /api/alerts/test 결과 — 채널별 성공 여부 */
export interface AlertTestResponse {
  channels: string[];
  results: Record<string, boolean>;
  detail: string;
}

/** GET /api/alerts/history 항목 — **실제로 알림으로 나간** 전환 1건 */
export interface AlertHistoryItem {
  id: number;
  notified_at: string;
  code: string;
  name: string;
  view_kind: string;
  before_view: string;
  after_view: string;
  close: number | null;
  change_pct: number | null;
  /** 발송에 성공한 채널만 콤마로 이은 값 */
  channels: string;
}

export interface AlertHistoryResponse {
  items: AlertHistoryItem[];
}
