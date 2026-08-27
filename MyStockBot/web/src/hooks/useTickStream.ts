import { useEffect, useState } from "react";
import { getApiToken } from "../api";
import type { LiveBar, Timeframe } from "../types";

// ⚠️ 보안 주의: token을 ?token= query parameter로 전달하므로 브라우저 DevTools 및
// 서버 로그(access log 등)에 평문으로 노출될 수 있다. WebSocket 표준상 Authorization
// 헤더를 지원하지 않으므로 이것이 유일한 방식이지만, 토큰이 민감한 환경에서는 이
// 설계의 위험을 인식하고 사용할 것.

/** 서버가 발행하는 체결 틱 1건 — server/services/kis_ws.py 이벤트 스키마와 1:1 대응 */
export interface TickData {
  code: string;
  price: number;
  change: number;
  changePct: number;
  volume: number | null;
  /** 체결시각 HH:MM:SS (KIS 원시값) */
  time: string;
  /** 이 틱을 브라우저가 수신한 시각(ms, Date.now()) — 카드 플래시 트리거 키로만 사용 */
  receivedAt: number;
}

export interface UseTickStreamResult {
  /** 종목코드 → 최신 틱. 수신된 적 있는 종목만 키로 존재(장외 등 틱이 없으면 빈 객체일 수 있음) */
  ticks: Record<string, TickData>;
  /** 브라우저 ↔ 서버 WS 연결 상태 */
  connected: boolean;
  /** 서버 ↔ KIS 실시간 시세 연결 상태(status 이벤트 기준). 장외엔 서버가 KIS에 연결돼 있어도 틱이 없는 게 정상 */
  kisConnected: boolean;
  /**
   * KIS 세션 구독 한도(41건)에 걸려 실시간에서 제외된 종목 코드.
   * 관심종목이 추가 순으로 잘리므로 **가장 최근에 추가한 종목**이 여기 들어간다.
   * 연결이 끊겨도 비우지 않는다 — 제외 사실 자체는 여전히 참이고, 재연결마다
   * 안내가 깜빡이는 편이 더 혼란스럽다.
   */
  excludedCodes: Set<string>;
  /**
   * 종목코드 → 타임프레임별 진행중(미마감) 봉. bar_update 를 못 받은 종목·tf 는 키가 없다.
   * 재연결로 WS 가 잠시 끊겨도 지우지 않는다(ticks 와 같은 원칙 — 재연결 즉시 다시 찬다).
   */
  liveBars: Record<string, Partial<Record<Timeframe, LiveBar>>>;
}

/** bar_update.tf 허용값 — candles API 의 Timeframe 중 1w/1M/1y 는 이 메시지로 오지 않는다 */
const VALID_BAR_TFS: ReadonlySet<string> = new Set([
  "1m", "5m", "15m", "30m", "60m", "120m", "240m", "1d",
]);

interface RawBarUpdateMessage {
  type: "bar_update";
  code: string;
  tf: Timeframe;
  bar: Record<string, unknown>;
}

function isRawBarUpdateMessage(data: unknown): data is RawBarUpdateMessage {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  return (
    obj.type === "bar_update" &&
    typeof obj.code === "string" &&
    typeof obj.tf === "string" &&
    VALID_BAR_TFS.has(obj.tf) &&
    typeof obj.bar === "object" &&
    obj.bar !== null
  );
}

/** 전 필드가 유효한 숫자일 때만 LiveBar 로 승격한다.
 * 서버 계약상 결측이 없어야 하지만, 반쯤 찬 봉이 차트에 들어가면 캔들이 깨지므로 방어한다. */
function parseLiveBar(raw: Record<string, unknown>): LiveBar | null {
  const { t, open, high, low, close, volume } = raw;
  if (
    typeof t === "number" && typeof open === "number" && typeof high === "number" &&
    typeof low === "number" && typeof close === "number" && typeof volume === "number"
  ) {
    return { t, open, high, low, close, volume };
  }
  return null;
}

const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;

/** VITE_API_BASE가 있으면 그 host를 ws(s)://로 변환, 없으면 현재 origin 기준 상대 경로(dev 프록시가 처리). */
function buildWsBase(): string {
  const apiBase = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
  if (apiBase) {
    return apiBase.replace(/^https/, "wss").replace(/^http/, "ws");
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}

interface RawTickMessage {
  type: "tick";
  code: string;
  price: number;
  change?: unknown;
  change_pct?: unknown;
  volume?: unknown;
  time?: unknown;
}

function isRawTickMessage(data: unknown): data is RawTickMessage {
  if (typeof data !== "object" || data === null) {
    return false;
  }
  const obj = data as Record<string, unknown>;
  return (
    obj.type === "tick" &&
    typeof obj.code === "string" &&
    typeof obj.price === "number"
  );
}

/**
 * 서버 /ws/ticks 구독 — KIS 실시간 체결 틱을 브라우저로 중계.
 * 장외 시간엔 틱 자체가 없는 게 정상(연결은 유지될 수 있음). 연결이 끊기면 지수 백오프(1s→30s)로
 * 재연결하며, 매 재연결 시도마다 localStorage의 최신 토큰을 다시 읽는다(토큰 갱신 반영).
 */
export function useTickStream(): UseTickStreamResult {
  const [ticks, setTicks] = useState<Record<string, TickData>>({});
  const [connected, setConnected] = useState(false);
  const [kisConnected, setKisConnected] = useState(false);
  const [excludedCodes, setExcludedCodes] = useState<Set<string>>(() => new Set());
  const [liveBars, setLiveBars] = useState<
    Record<string, Partial<Record<Timeframe, LiveBar>>>
  >({});

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let backoffMs = INITIAL_BACKOFF_MS;
    const wsBase = buildWsBase();

    function buildUrl(): string {
      const token = getApiToken();
      const path = `${wsBase}/ws/ticks`;
      return token ? `${path}?token=${encodeURIComponent(token)}` : path;
    }

    function scheduleReconnect() {
      if (cancelled) return;
      reconnectTimer = window.setTimeout(() => {
        backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
        connect();
      }, backoffMs);
    }

    // 장중엔 종목×tf 수십 건이 2초 주기로 몰린다. 메시지마다 setState 하지 않고 같은
    // 애니메이션 프레임에 도착한 갱신을 하나로 합쳐 1회만 반영한다(리렌더 폭풍 방지).
    let pendingLiveBars: Record<string, Partial<Record<Timeframe, LiveBar>>> | null = null;
    let flushRafId: number | null = null;

    function scheduleLiveBarsFlush() {
      if (flushRafId !== null) return;
      flushRafId = window.requestAnimationFrame(() => {
        flushRafId = null;
        const pending = pendingLiveBars;
        pendingLiveBars = null;
        if (!pending || cancelled) return;
        setLiveBars((prev) => {
          const next: Record<string, Partial<Record<Timeframe, LiveBar>>> = { ...prev };
          for (const code of Object.keys(pending)) {
            next[code] = { ...next[code], ...pending[code] };
          }
          return next;
        });
      });
    }

    function connect() {
      if (cancelled) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(buildUrl());
      } catch {
        // 브라우저가 WS 생성 자체를 거부하는 극히 드문 경우(잘못된 URL 등) — 백오프 후 재시도
        scheduleReconnect();
        return;
      }
      socket = ws;

      ws.onopen = () => {
        if (cancelled) return;
        backoffMs = INITIAL_BACKOFF_MS;
        setConnected(true);
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        let parsed: unknown;
        try {
          parsed = JSON.parse(String(event.data));
        } catch {
          return;
        }
        if (!parsed || typeof parsed !== "object") return;
        const data = parsed as Record<string, unknown>;

        if (isRawTickMessage(data)) {
          const tick: TickData = {
            code: data.code,
            price: data.price,
            change: typeof data.change === "number" ? data.change : 0,
            changePct: typeof data.change_pct === "number" ? data.change_pct : 0,
            volume: typeof data.volume === "number" ? data.volume : null,
            time: typeof data.time === "string" ? data.time : "",
            receivedAt: Date.now(),
          };
          setTicks((prev) => ({ ...prev, [tick.code]: tick }));
        } else if (isRawBarUpdateMessage(data)) {
          const bar = parseLiveBar(data.bar);
          if (bar) {
            if (!pendingLiveBars) pendingLiveBars = {};
            pendingLiveBars[data.code] = {
              ...pendingLiveBars[data.code],
              [data.tf]: bar,
            };
            scheduleLiveBarsFlush();
          }
        } else if (data.type === "status") {
          setKisConnected(Boolean(data.kis_connected));
          // excluded 는 구버전 서버엔 없다 — 배열일 때만 반영한다.
          if (Array.isArray(data.excluded)) {
            const next: string[] = data.excluded.filter(
              (c: unknown): c is string => typeof c === "string"
            );
            setExcludedCodes((prev) => {
              // 내용이 같으면 같은 참조를 유지해 불필요한 리렌더를 막는다.
              if (prev.size === next.length && next.every((c) => prev.has(c))) {
                return prev;
              }
              return new Set(next);
            });
          }
        }
      };

      ws.onerror = () => {
        // close 이벤트가 뒤이어 발생해 재연결을 트리거하므로 여기서는 별도 처리 없음
      };

      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        setKisConnected(false);
        scheduleReconnect();
      };
    }

    // 탭이 백그라운드에서 복귀했을 때 연결이 끊겨 있으면 백오프 타이머 만료를
    // 기다리지 않고 즉시 재연결(백오프 리셋)한다.
    function handleVisibilityChange() {
      if (cancelled || document.visibilityState !== "visible") return;
      const isDisconnected =
        !socket ||
        socket.readyState === WebSocket.CLOSED ||
        socket.readyState === WebSocket.CLOSING;
      if (!isDisconnected) return;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      backoffMs = INITIAL_BACKOFF_MS;
      connect();
    }

    connect();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      cancelled = true;
      if (flushRafId !== null) {
        window.cancelAnimationFrame(flushRafId);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
      }
    };
  }, []);

  return { ticks, connected, kisConnected, excludedCodes, liveBars };
}
