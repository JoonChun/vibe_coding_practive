// ── eventStream.ts — SSE 클라이언트 래퍼 (PHASE-1-SPEC.md §3, M2.2) ──────────
// 브라우저 EventSource를 감싸며 자동 재연결·정리 함수를 제공한다.
// 브라우저 EventSource는 last-event-id를 자동으로 헤더에 포함시키므로
// 별도 구현 불필요.

import type { AgentEvent } from "@/types/events";

/**
 * SSE 스트림 연결을 열고 이벤트를 구독한다.
 *
 * @param onEvent         이벤트 수신 콜백
 * @param onConnectionChange  연결 상태 변경 콜백 (true = 연결, false = 끊김)
 * @returns 정리 함수 (useEffect return 값으로 사용)
 *
 * @example
 *   useEffect(() => {
 *     const cleanup = createEventStream(addEvent, setConnected);
 *     return cleanup;
 *   }, []);
 */
export function createEventStream(
  onEvent: (e: AgentEvent) => void,
  onConnectionChange?: (connected: boolean) => void
): () => void {
  let eventSource: EventSource | null = null;
  let cancelled = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (cancelled) return;

    eventSource = new EventSource("/api/events");

    eventSource.onopen = () => {
      onConnectionChange?.(true);
    };

    eventSource.onmessage = (e: MessageEvent<string>) => {
      try {
        const event = JSON.parse(e.data) as AgentEvent;
        onEvent(event);
      } catch {
        // malformed data — skip
      }
    };

    eventSource.onerror = () => {
      onConnectionChange?.(false);
      eventSource?.close();
      eventSource = null;

      // 3초 후 재연결 (SSE 연결 끊김 §12 완화 전략)
      if (!cancelled) {
        reconnectTimer = setTimeout(connect, 3_000);
      }
    };
  };

  connect();

  // 정리 함수 반환
  return () => {
    cancelled = true;
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    eventSource?.close();
    eventSource = null;
    onConnectionChange?.(false);
  };
}
