import { useEffect, useState } from "react";
import { getCandles } from "../api";

/**
 * 종목의 최근 일봉 종가 배열을 조회해 스파크라인 렌더링에 사용한다.
 * 실패하거나 2개 미만이면 null을 반환해 호출부에서 스파크라인을 숨기도록 한다.
 */
export function useSparkline(code: string, limit = 20): number[] | null {
  const [closes, setCloses] = useState<number[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCloses(null);

    getCandles(code, "1d", limit)
      .then((res) => {
        if (cancelled) return;
        const values = res.items
          .map((item) => item.close)
          .filter((close): close is number => typeof close === "number" && Number.isFinite(close));
        setCloses(values.length >= 2 ? values : null);
      })
      .catch(() => {
        if (!cancelled) setCloses(null);
      });

    return () => {
      cancelled = true;
    };
  }, [code, limit]);

  return closes;
}
