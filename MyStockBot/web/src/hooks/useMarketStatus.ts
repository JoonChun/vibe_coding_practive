import { useCallback, useEffect, useRef, useState } from "react";
import { getMarketStatus } from "../api";
import type { MarketStatus } from "../types";

/** 상태 자체는 분 단위로만 바뀌므로 폴링은 느슨하게. */
const POLL_INTERVAL_MS = 60_000;
/** 카운트다운은 서버가 준 세션 경계로 로컬에서 매초 계산한다(서버 폴링 불필요). */
const TICK_INTERVAL_MS = 1_000;

export interface UseMarketStatusResult {
  data: MarketStatus | null;
  /** 남은 시간(밀리초). 장전·장중이면 다음 경계까지, 그 외 null */
  remainingMs: number | null;
  /** 남은 시간이 무엇까지인지 — "close"(마감까지) | "open"(개장까지) */
  countdownTarget: "close" | "open" | null;
  error: string | null;
  refresh: () => void;
}

function computeCountdown(
  data: MarketStatus | null,
  nowMs: number
): { remainingMs: number | null; countdownTarget: "close" | "open" | null } {
  if (!data) return { remainingMs: null, countdownTarget: null };

  // 장중이면 마감까지, 그 외(장전·장마감·휴장)에는 다음 개장까지 센다.
  const target = data.status === "open" ? "close" : "open";
  const boundary = target === "close" ? data.session_close : data.session_open;
  const boundaryMs = Date.parse(boundary);
  if (Number.isNaN(boundaryMs)) return { remainingMs: null, countdownTarget: null };

  const remaining = boundaryMs - nowMs;
  // 경계를 지났으면 카운트다운을 감춘다 — 다음 폴링이 상태를 갱신할 때까지 음수를 보이지 않게.
  if (remaining <= 0) return { remainingMs: null, countdownTarget: null };
  return { remainingMs: remaining, countdownTarget: target };
}

/**
 * 장 운영 상태 훅.
 *
 * 서버가 세션 경계(session_open/close)를 ISO8601 로 내려주고, 카운트다운은 여기서
 * 로컬 시계로 계산한다. 초 단위 표시를 위해 서버를 초당 폴링하지 않기 위함이다.
 * 서버 시각(server_time)과 브라우저 시각의 차이를 보정해 기기 시계가 틀어져 있어도
 * 남은 시간이 어긋나지 않게 한다.
 */
export function useMarketStatus(): UseMarketStatusResult {
  const [data, setData] = useState<MarketStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  /** 서버 시각 − 브라우저 시각. 기기 시계 오차 보정용. */
  const clockSkewRef = useRef(0);
  const inFlightRef = useRef(false);

  const fetchStatus = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const res = await getMarketStatus();
      const serverMs = Date.parse(res.server_time);
      if (!Number.isNaN(serverMs)) {
        clockSkewRef.current = serverMs - Date.now();
      }
      setData(res);
      setError(null);
    } catch {
      // 상태 배지는 부가 정보다 — 실패해도 마지막 값을 유지하고 화면을 막지 않는다.
      setError("장 운영 상태를 불러오지 못했습니다.");
    } finally {
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    void fetchStatus();
    const id = window.setInterval(() => {
      void fetchStatus();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [fetchStatus]);

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), TICK_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  const { remainingMs, countdownTarget } = computeCountdown(
    data,
    nowMs + clockSkewRef.current
  );

  return { data, remainingMs, countdownTarget, error, refresh: fetchStatus };
}
