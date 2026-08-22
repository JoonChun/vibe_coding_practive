import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getAlertConfig, getAlertState, sendTestAlert } from "../api";
import type { AlertConfig, AlertStateResponse, AlertTestResponse } from "../types";

export interface UseAlertsResult {
  config: AlertConfig | null;
  state: AlertStateResponse | null;
  loading: boolean;
  error: string | null;
  errorStatus: number | null;
  refresh: () => void;
  /** 테스트 발송 진행 중 */
  testing: boolean;
  testResult: AlertTestResponse | null;
  testError: string | null;
  runTest: () => void;
}

/**
 * 알림 설정·기준선 조회 + 테스트 발송.
 *
 * 폴링하지 않는다 — 설정은 `.env` 라서 서버를 재시작해야 바뀌고, 기준선은 수집 사이클에
 * 맞춰 느리게 움직인다. 사용자가 새로고침 버튼을 누를 때만 다시 읽는다.
 */
export function useAlerts(): UseAlertsResult {
  const [config, setConfig] = useState<AlertConfig | null>(null);
  const [state, setState] = useState<AlertStateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<AlertTestResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const inFlightRef = useRef(false);

  const load = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    try {
      // 기준선 조회가 실패해도 설정은 보여준다 — 둘의 실패 이유가 다를 수 있다.
      const [cfg, st] = await Promise.all([
        getAlertConfig(),
        getAlertState().catch(() => null),
      ]);
      setConfig(cfg);
      setState(st);
      setError(null);
      setErrorStatus(null);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : null;
      setErrorStatus(status);
      setError(
        e instanceof ApiError ? e.message : "알림 설정을 불러오지 못했습니다."
      );
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runTest = useCallback(async () => {
    setTesting(true);
    setTestError(null);
    setTestResult(null);
    try {
      setTestResult(await sendTestAlert());
    } catch (e) {
      // 429 = 이미 진행 중(서버가 동시 1건으로 제한). 그 문구를 그대로 보여준다.
      setTestError(
        e instanceof ApiError ? e.message : "테스트 발송에 실패했습니다."
      );
    } finally {
      setTesting(false);
      // 발송이 기준선을 건드리지는 않지만, 채널 인식 여부가 바뀌었을 수 있어 다시 읽는다.
      void load();
    }
  }, [load]);

  return {
    config, state, loading, error, errorStatus, refresh: load,
    testing, testResult, testError, runTest,
  };
}
