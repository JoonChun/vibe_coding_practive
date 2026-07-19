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

/** 눌림목 판정 — 정확히 6종(백엔드 schemas.py와 1:1). 점수엔 미반영, 정보성 전용(장기/일봉 개념). */
export type PullbackStatus =
  | "데이터부족"
  | "추세아님"
  | "추세지속"
  | "눌림 진행중(관망)"
  | "눌림목 반등(매수후보)"
  | "눌림 이탈(무효)";

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

/** 눌림목 체크리스트 항목 — 순서 고정 6개(백엔드 schemas.py와 1:1, 정배열→기울기→추세강도→근접→거래량수축→반등트리거) */
export interface PullbackCheck {
  label: string;
  ok: boolean;
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
  /** additive 신규 필드(눌림목 판정) — 장기(일봉) 개념, 점수엔 미반영(정보성 전용) */
  pullback_status: PullbackStatus | null;
  pullback_reason: string | null;
  pullback_trend_up: boolean | null;
  /** 눌림목 조건 체크리스트 — "데이터부족" 상태면 빈 배열, 구버전 응답이면 undefined/null일 수 있음 */
  pullback_checks?: PullbackCheck[] | null;
}

/** WS bar_update로 계속 갱신되는 실시간 참고 판정 — 확정 판정(short_view/long_view)과는 별개.
 * updated_at은 short/long 공통 1개(둘 다 같은 순간 재계산됨). null이면 아직 이 종목의 참고 판정이
 * 계산되지 않은 것(워밍업)이며, 오류와 구분할 근거 데이터가 없어 프론트에서 heuristic으로 판정한다
 * (docs/wireframes/phase2v2-live-ui.md §2 참조). */
export interface LiveJudgment {
  short_view_live: SignalView | null;
  short_score_live: number | null;
  long_view_live: SignalView | null;
  long_score_live: number | null;
  updated_at: string | null;
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
  /** additive 신규 필드(Phase 2 v2) — 백엔드가 아직 안 내려주면 undefined일 수 있음 */
  live?: LiveJudgment | null;
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

/** WS `bar_update`가 실어나르는 진행중(미마감) 봉 1개 — CandleItem과 달리 결측 없이 항상 값이 채워진다.
 * tf ∈ {1m,5m,15m,30m,60m,120m,240m,1d} (1w/1M/1y는 이 메시지에 오지 않음). */
export interface LiveBar {
  t: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
