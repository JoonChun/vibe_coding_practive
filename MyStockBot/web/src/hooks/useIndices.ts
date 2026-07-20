import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getIndices } from "../api";
import type { IndicesResponse } from "../types";

const POLL_INTERVAL_MS = 30_000;

export interface UseIndicesResult {
  data: IndicesResponse | null;
  loading: boolean;
  error: string | null;
  errorStatus: number | null;
  stale: boolean;
  refresh: () => void;
}

/** 코스피/코스닥 지수 폴링(30초). useSnapshot 과 동일한 stale-on-error 정책. */
export function useIndices(): UseIndicesResult {
  const [data, setData] = useState<IndicesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [stale, setStale] = useState(false);

  const inFlightRef = useRef(false);
  const dataRef = useRef<IndicesResponse | null>(null);

  const fetchIndices = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    try {
      const res = await getIndices();
      dataRef.current = res;
      setData(res);
      setError(null);
      setErrorStatus(null);
      setStale(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "지수를 불러오지 못했습니다.");
      setErrorStatus(e instanceof ApiError ? e.status : null);
      setStale(dataRef.current !== null);
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    void fetchIndices();
    const id = window.setInterval(() => {
      void fetchIndices();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [fetchIndices]);

  const refresh = useCallback(() => {
    void fetchIndices();
  }, [fetchIndices]);

  return { data, loading, error, errorStatus, stale, refresh };
}
