import { createContext, useContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';

const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/logs';
const WS_RECONNECT_DELAY_MS = 3000;

export interface LogEntry {
  time: string;
  msg: string;
  level: string;
}

export type EmailStatus = 'success' | 'error' | null;

interface BrewContextValue {
  logs: LogEntry[];
  isBrewing: boolean;
  currentStepIndex: number;
  emailStatus: EmailStatus;
  emailError: string;
  clearLogs: () => void;
  clearEmailStatus: () => void;
  startBrew: () => Promise<void>;
}

const BrewContext = createContext<BrewContextValue | null>(null);

export const useBrewContext = () => {
  const ctx = useContext(BrewContext);
  if (!ctx) throw new Error('useBrewContext must be used inside BrewProvider');
  return ctx;
};

const STEP_IDS = ['collect', 'sheet', 'summary', 'mail'] as const;
const STEP_KEYWORDS: Record<string, string[]> = {
  collect: ['뉴스 수집'],
  sheet: ['Google Sheets', 'Sheets'],
  summary: ['AI 요약', '요약 완료'],
  mail: ['이메일', '메일'],
};

function detectStep(msg: string): string | null {
  for (const [step, keywords] of Object.entries(STEP_KEYWORDS)) {
    if (keywords.some(k => msg.includes(k))) return step;
  }
  return null;
}

function parseTimestamp(ts: string): string {
  const d = new Date(ts);
  return isNaN(d.getTime())
    ? new Date().toLocaleTimeString('ko-KR', { hour12: false })
    : d.toLocaleTimeString('ko-KR', { hour12: false });
}

export function BrewProvider({ children }: { children: ReactNode }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isBrewing, setIsBrewing] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(-1);
  const [emailStatus, setEmailStatus] = useState<EmailStatus>(null);
  const [emailError, setEmailError] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as { timestamp: string; level: string; message: string };
        const time = parseTimestamp(data.timestamp);
        const msg = data.message;

        setLogs(prev => [...prev, { time, msg, level: data.level }]);

        const step = detectStep(msg);
        if (step) {
          const idx = STEP_IDS.indexOf(step as typeof STEP_IDS[number]);
          if (idx >= 0) setCurrentStepIndex(idx);
        }

        if (msg.includes('✉️ 이메일 발송 완료')) {
          setEmailStatus('success');
        } else if (msg.includes('이메일 발송 실패')) {
          setEmailStatus('error');
          setEmailError(msg.replace('이메일 발송 실패: ', ''));
        }

        if (msg.includes('브루잉 완료') || msg.includes('브루잉 실패')) {
          setIsBrewing(false);
        }
      } catch {}
    };

    ws.onerror = () => setIsBrewing(false);

    ws.onclose = () => {
      reconnectTimerRef.current = setTimeout(connectWebSocket, WS_RECONNECT_DELAY_MS);
    };
  }, []);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  const startBrew = async () => {
    if (isBrewing) return;
    setLogs([]);
    setCurrentStepIndex(-1);
    setEmailStatus(null);
    setIsBrewing(true);
    try {
      const res = await fetch(`${API_BASE}/api/brew/start`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '브루잉 시작 실패' }));
        setLogs([{ time: new Date().toLocaleTimeString('ko-KR', { hour12: false }), msg: err.detail, level: 'ERROR' }]);
        setIsBrewing(false);
      }
    } catch {
      setLogs([{ time: new Date().toLocaleTimeString('ko-KR', { hour12: false }), msg: '백엔드 연결 실패. 서버가 실행 중인지 확인하세요.', level: 'ERROR' }]);
      setIsBrewing(false);
    }
  };

  const clearLogs = () => {
    setLogs([]);
    setCurrentStepIndex(-1);
  };

  const clearEmailStatus = () => {
    setEmailStatus(null);
    setEmailError('');
  };

  return (
    <BrewContext.Provider value={{ logs, isBrewing, currentStepIndex, emailStatus, emailError, clearLogs, clearEmailStatus, startBrew }}>
      {children}
    </BrewContext.Provider>
  );
}
