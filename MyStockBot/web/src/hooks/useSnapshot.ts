import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getSnapshot } from "../api";
import type { SnapshotResponse } from "../types";

const POLL_INTERVAL_MS = 20_000;

export interface UseSnapshotResult {
  data: SnapshotResponse | null;
  loading: boolean;
  error: string | null;
  /** 폴링 실패 후에도 마지막으로 성공한 데이터를 유지 중일 때 true */
  stale: boolean;
  lastUpdatedAt: Date | null;
  refresh: () => void;
}

export function useSnapshot(): UseSnapshotResult {
  const [data, setData] = useState<SnapshotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
      setStale(false);
      setLastUpdatedAt(new Date());
    } catch (e) {
      const message =
        e instanceof ApiError ? e.message : "알 수 없는 오류가 발생했습니다";
      setError(message);
      // 실패 시 기존 데이터는 유지하고 stale 플래그만 세움
      setStale(dataRef.current !== null);
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    void fetchSnapshot();
    const id = window.setInterval(() => {
      void fetchSnapshot();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [fetchSnapshot]);

  const refresh = useCallback(() => {
    void fetchSnapshot();
  }, [fetchSnapshot]);

  return { data, loading, error, stale, lastUpdatedAt, refresh };
}
