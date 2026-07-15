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

export interface BarItem {
  date: string; // YYYY-MM-DD
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface StockBarsResponse {
  code: string;
  items: BarItem[];
}
