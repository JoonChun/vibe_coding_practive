import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getSnapshot } from "../api";
import type { SnapshotResponse } from "../types";

const POLL_INTERVAL_MS = 20_000;

export interface UseSnapshotResult {
  data: SnapshotResponse | null;
  loading: boolean;
  error: string | null;
  /** 마지막 오류가 ApiError였을 경우의 HTTP 상태 코드 (예: 401) */
  errorStatus: number | null;
  /** 폴링 실패 후에도 마지막으로 성공한 데이터를 유지 중일 때 true */
  stale: boolean;
  /**
   * 서버는 살아서 응답했지만 **첫 수집 사이클이 아직 끝나지 않은** 상태.
   *
   * 백엔드가 이미 구분해 보내주고 있다 — 관심종목이 0개면 상태가 채워져 cache_hit=true
   * (빈 목록이 정답), 부팅 직후 첫 사이클 전이면 cache_hit=false 다. 이 둘을 같은
   * "데이터 없음"으로 렌더하면 정상 워밍업이 설정 오류처럼 읽힌다.
   */
  warmingUp: boolean;
  lastUpdatedAt: Date | null;
  refresh: () => void;
}

export function useSnapshot(): UseSnapshotResult {
  const [data, setData] = useState<SnapshotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [stale, setStale] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  const inFlightRef = useRef(false);
  const dataRef = useRef<SnapshotResponse | null>(null);

  const fetchSnapshot = useCallback(async () => {
    // 요청 중복 방지: 이미 진행 중인 폴링/수동 새로고침이 있으면 건너뜀
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    try {
      const res = await getSnapshot();
      dataRef.current = res;
      setData(res);
      setError(null);
      setErrorStatus(null);
      setStale(false);
      setLastUpdatedAt(new Date());
    } catch (e) {
      const message =
        e instanceof ApiError ? e.message : "알 수 없는 오류가 발생했습니다";
      setError(message);
      setErrorStatus(e instanceof ApiError ? e.status : null);
      // 실패 시 기존 데이터는 유지하고 stale 플래그만 세움
      setStale(dataRef.current !== null);
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    let id = 0;
    const start = () => {
      if (!id) id = window.setInterval(() => void fetchSnapshot(), POLL_INTERVAL_MS);
    };
    const stop = () => {
      if (id) {
        window.clearInterval(id);
        id = 0;
      }
    };
    // 숨은 탭에서는 폴링을 멈춰 불필요한 네트워크/배터리 소모를 막고, 다시 보일 때 즉시 갱신.
    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        void fetchSnapshot();
        start();
      }
    };
    void fetchSnapshot();
    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [fetchSnapshot]);

  const refresh = useCallback(() => {
    void fetchSnapshot();
  }, [fetchSnapshot]);

  const warmingUp = data !== null && data.cache_hit === false;

  return { data, loading, error, errorStatus, stale, warmingUp, lastUpdatedAt, refresh };
}
