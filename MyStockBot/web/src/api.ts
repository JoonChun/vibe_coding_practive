import type {
  AlertConfig,
  AlertStateResponse,
  AlertTestResponse,
  BacktestResponse,
  CandlesResponse,
  DcaResponse,
  IndicesResponse,
  MarketStatus,
  PaperAccount,
  PaperOrderInput,
  PaperTradesResponse,
  SnapshotResponse,
  StockSearchResponse,
  Timeframe,
  WatchlistItem,
  WatchlistItemInput,
  WatchlistListResponse,
} from "./types";

// 개발: 빈 값(상대경로) → vite dev 프록시(/api → localhost:8000)가 처리.
// 배포(Vercel 등): VITE_API_BASE에 백엔드 공개 URL을 설정.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

const TOKEN_STORAGE_KEY = "mystockbot_api_token";

/** 저장된 API 토큰 조회. localStorage 접근 불가(프라이빗 모드 등) 시 null. */
export function getApiToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

/** API 토큰 저장. */
export function setApiToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    // localStorage 접근 불가 시 무시
  }
}

/** API 토큰 삭제. */
export function clearApiToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // localStorage 접근 불가 시 무시
  }
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function extractErrorMessage(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof (body as { detail?: unknown }).detail === "string"
    ) {
      return (body as { detail: string }).detail;
    }
  } catch {
    // 응답 본문이 JSON이 아니거나 비어있는 경우 무시
  }
  return `요청이 실패했습니다 (${res.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    // ngrok 무료 플랜은 브라우저 요청에 경고 interstitial(HTML)을 끼워넣어 JSON 응답을
    // 가로챈다. 이 헤더가 있으면 곧바로 백엔드로 통과된다. 다른 백엔드는 무시하므로 무해.
    "ngrok-skip-browser-warning": "true",
    ...(init?.headers as Record<string, string> | undefined),
  };
  const token = getApiToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError(0, "서버에 연결할 수 없습니다");
  }

  if (!res.ok) {
    const message = await extractErrorMessage(res);
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export function getWatchlist(): Promise<WatchlistListResponse> {
  return request<WatchlistListResponse>("/api/watchlist");
}

export function addWatchlistItem(
  item: WatchlistItemInput
): Promise<WatchlistItem> {
  return request<WatchlistItem>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify(item),
  });
}

export function deleteWatchlistItem(code: string): Promise<void> {
  return request<void>(`/api/watchlist/${encodeURIComponent(code)}`, {
    method: "DELETE",
  });
}

export function getSnapshot(): Promise<SnapshotResponse> {
  return request<SnapshotResponse>("/api/snapshot");
}

/** 코스피·코스닥 시장 지수 조회 (메인 대시보드용). */
export function getIndices(): Promise<IndicesResponse> {
  return request<IndicesResponse>("/api/indices");
}

/** 장 운영 상태(장전/장중/장마감/휴장) + 세션 경계. 외부 조회 없는 순수 계산이라 가볍다. */
export function getMarketStatus(): Promise<MarketStatus> {
  return request<MarketStatus>("/api/market/status");
}

/** 모의투자 가상 계좌(현금·평가손익·보유목록) 조회. */
export function getPaperAccount(): Promise<PaperAccount> {
  return request<PaperAccount>("/api/paper/account");
}

/** 모의투자 거래 내역 조회. */
export function getPaperTrades(limit = 100): Promise<PaperTradesResponse> {
  return request<PaperTradesResponse>(`/api/paper/trades?limit=${limit}`);
}

/** 모의투자 매수/매도 주문(현재가 기준 즉시 체결). 갱신된 계좌 반환. */
export function placePaperOrder(order: PaperOrderInput): Promise<PaperAccount> {
  return request<PaperAccount>("/api/paper/orders", {
    method: "POST",
    body: JSON.stringify(order),
  });
}

/** 모의투자 계좌 초기화. */
export function resetPaperAccount(): Promise<PaperAccount> {
  return request<PaperAccount>("/api/paper/reset", { method: "POST" });
}

/** 전 종목 자동완성 검색(종목명 부분일치 또는 코드 prefix). limit 기본 10·최대 30. */
export function searchStocks(
  q: string,
  limit = 10
): Promise<StockSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return request<StockSearchResponse>(`/api/stocks/search?${params.toString()}`);
}

/** 판정 백테스트 조회 — 과거 판정 재적용 적중률·가상수익률. horizon 기본 20거래일. */
export function getBacktest(
  code: string,
  horizon = 20
): Promise<BacktestResponse> {
  return request<BacktestResponse>(
    `/api/stocks/${encodeURIComponent(code)}/backtest?horizon=${horizon}`
  );
}

/** 적립식 백테스트 — 정기 매수 시뮬레이션.
 * mode qty(주수)/amount(금액), freq 주기(주/월/분기), reinvest 배당 재투자(현재 백엔드 미반영). */
export function getDca(
  code: string,
  opts: {
    mode?: "qty" | "amount";
    per?: number;
    months?: number;
    freq?: "weekly" | "monthly" | "quarterly";
    reinvest?: boolean;
  } = {}
): Promise<DcaResponse> {
  const { mode = "qty", per = 1, months = 120, freq = "monthly", reinvest = false } = opts;
  const params = new URLSearchParams({
    mode,
    per: String(per),
    months: String(months),
    freq,
    reinvest: String(reinvest),
  });
  return request<DcaResponse>(
    `/api/stocks/${encodeURIComponent(code)}/dca?${params.toString()}`
  );
}

/** 종목 캔들 히스토리 조회(멀티 타임프레임). count 기본 150·최대 300(마지막 N개). */
export function getCandles(
  code: string,
  tf: Timeframe = "1d",
  count = 150
): Promise<CandlesResponse> {
  const params = new URLSearchParams({ tf, count: String(count) });
  return request<CandlesResponse>(
    `/api/stocks/${encodeURIComponent(code)}/candles?${params.toString()}`
  );
}

/** 알림 설정 조회(읽기 전용 — 설정은 .env 로 바꾼다). 비밀은 응답에 실리지 않는다. */
export function getAlertConfig(): Promise<AlertConfig> {
  return request<AlertConfig>("/api/alerts/config");
}

/** 저장된 기준선("마지막으로 알린 판정") 조회 — 오알림 진단용. */
export function getAlertState(): Promise<AlertStateResponse> {
  return request<AlertStateResponse>("/api/alerts/state");
}

/**
 * 테스트 발송. ENABLED 플래그와 장 시간대 게이트를 우회한다 — 설정을 켜기 전에
 * 채널이 살아 있는지 확인하는 것이 목적이다. 서버가 동시 1건으로 제한한다(429).
 */
export function sendTestAlert(): Promise<AlertTestResponse> {
  return request<AlertTestResponse>("/api/alerts/test", { method: "POST" });
}
