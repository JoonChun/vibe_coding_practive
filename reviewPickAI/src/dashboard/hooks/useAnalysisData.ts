import { useState, useEffect, useCallback } from 'react';
import type { AnalysisResult, ComparisonSession } from '@/types';
import { STORAGE_KEYS } from '@/constants';

interface UseAnalysisDataReturn {
  data: AnalysisResult | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
  comparisonSessions: ComparisonSession[];
}

export function useAnalysisData(): UseAnalysisDataReturn {
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [comparisonSessions, setComparisonSessions] = useState<ComparisonSession[]>([]);

  const fetch = useCallback(() => {
    setLoading(true);
    chrome.storage.local.get(
      [STORAGE_KEYS.CURRENT_ANALYSIS, STORAGE_KEYS.COMPARISON_SESSIONS],
      (result) => {
        const analysis = result[STORAGE_KEYS.CURRENT_ANALYSIS] as AnalysisResult | undefined;
        const sessions = result[STORAGE_KEYS.COMPARISON_SESSIONS] as ComparisonSession[] | undefined;
        if (chrome.runtime.lastError) {
          setError(chrome.runtime.lastError.message ?? '스토리지 오류');
        } else {
          setData(analysis ?? null);
          setComparisonSessions(sessions ?? []);
          setError(null);
        }
        setLoading(false);
      },
    );
  }, []);

  useEffect(() => {
    fetch();

    // chrome.storage 변경 구독 → 재분석/비교 세션 추가 시 자동 업데이트
    const listener = (
      changes: Record<string, chrome.storage.StorageChange>,
    ) => {
      if (STORAGE_KEYS.CURRENT_ANALYSIS in changes) {
        const newVal = changes[STORAGE_KEYS.CURRENT_ANALYSIS].newValue as AnalysisResult | undefined;
        setData(newVal ?? null);
        setLoading(false);
      }
      if (STORAGE_KEYS.COMPARISON_SESSIONS in changes) {
        const newSessions = changes[STORAGE_KEYS.COMPARISON_SESSIONS].newValue as ComparisonSession[] | undefined;
        setComparisonSessions(newSessions ?? []);
      }
    };

    chrome.storage.local.onChanged.addListener(listener);
    return () => chrome.storage.local.onChanged.removeListener(listener);
  }, [fetch]);

  return { data, loading, error, refetch: fetch, comparisonSessions };
}
