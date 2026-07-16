import { useEffect, useRef, useState } from "react";

const FLASH_DURATION_MS = 300;

export type TickFlashDirection = "up" | "down" | null;

/**
 * 틱 수신 시 300ms짜리 배경 플래시 CSS 클래스명을 반환한다(상승 tick-flash-up / 하락 tick-flash-down).
 * key(보통 tick.receivedAt)가 바뀔 때마다 재발화하며, direction이 null(보합·틱 없음)이면 발화하지 않는다.
 * prefers-reduced-motion 대응은 CSS(@media prefers-reduced-motion) 쪽에서 animation: none으로 처리한다.
 */
export function useTickFlash(
  direction: TickFlashDirection,
  key: number | string | null | undefined
): string | null {
  const [flashClass, setFlashClass] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!direction || key === null || key === undefined) return;
    setFlashClass(direction === "up" ? "tick-flash-up" : "tick-flash-down");
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setFlashClass(null), FLASH_DURATION_MS);
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
    // key(신규 틱 수신)가 바뀔 때만 재발화 — direction은 같은 렌더에서 key와 함께 최신값으로 갱신됨
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return flashClass;
}
