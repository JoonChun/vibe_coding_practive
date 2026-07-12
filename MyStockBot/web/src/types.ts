// 백엔드 API 스키마와 1:1 대응 (MyStockBot/server/schemas.py 참조)

export type SignalView =
  | "강력매수"
  | "매수"
  | "관망"
  | "매도"
  | "강력매도"
  | "데이터부족";

export type SnapshotSource = "kis" | "yfinance";

export interface WatchlistItem {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

export interface WatchlistListResponse {
  items: WatchlistItem[];
}

export interface WatchlistItemInput {
  code: string;
  name: string;
}

export interface SnapshotItem {
  code: string;
  name: string;
  close: number | null;
  short_view: SignalView | null;
  long_view: SignalView | null;
  source: SnapshotSource | null;
  error: string | null;
  factors: Record<string, unknown> | null;
}

export interface SnapshotResponse {
  generated_at: string;
  cache_hit: boolean;
  items: SnapshotItem[];
}
