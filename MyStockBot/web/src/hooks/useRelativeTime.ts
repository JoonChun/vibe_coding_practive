import { useEffect, useState } from "react";

/**
 * 주어진 시각을 "방금" / "3초 전" / "2분 전" 같은 상대 시간 문자열로 변환한다.
 * 내부적으로 1초 간격 재렌더를 트리거해 표시 값을 살아있게 유지한다.
 */
export function useRelativeTime(date: Date | null): string {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!date) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [date]);

  if (!date) return "";

  const diffSec = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (diffSec < 5) return "방금";
  if (diffSec < 60) return `${diffSec}초 전`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour}시간 전`;
  const diffDay = Math.round(diffHour / 24);
  return `${diffDay}일 전`;
}
