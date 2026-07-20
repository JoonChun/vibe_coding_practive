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
export interface IndexItem {
  code: string; // "KOSPI" | "KOSDAQ"
  name: string;
  value: number | null;
  change: number | null;
  change_pct: number | null;
  source: SnapshotSource | null;
  error: string | null;
}

export interface IndicesResponse {
  generated_at: string;
  cache_hit: boolean;
  items: IndexItem[];
}

/** 판정 백테스트 (GET /api/stocks/{code}/backtest) */
export interface BacktestSide {
  signals: number;
  hit_rate: number | null;
  avg_forward_pct: number | null;
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
  buy: BacktestSide;
  sell: BacktestSide;
  strategy_return_pct: number;
  buy_hold_return_pct: number;
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
  holdings: PaperHolding[];
}

export interface PaperTrade {
  id: number;
  ts: string;
  code: string;
  name: string;
  side: "buy" | "sell";
  qty: number;
  price: number;
  amount: number;
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
  short_score: number | null; // 단기 스코어 합 (임계 ±2)
  long_score: number | null; // 장기 스코어 합 (임계 ±3)
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
