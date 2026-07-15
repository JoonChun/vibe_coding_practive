import { useEffect, useState } from "react";
import { getStockBars } from "../api";
import type { BarItem } from "../types";

export interface UseBarsResult {
  items: BarItem[];
  loading: boolean;
  error: string | null;
}

/**
 * 종목의 일봉 히스토리(최근 N개)를 조회한다. 상세 페이지의 가격 차트·볼린저 시각화용.
 * 실패 시 items는 빈 배열로 유지되고 error 메시지가 채워진다(스냅샷 폴링과 무관하게 1회성 조회).
 */
export function useBars(code: string, limit = 60): UseBarsResult {
  const [items, setItems] = useState<BarItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) {
      setItems([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getStockBars(code, limit)
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setItems([]);
        setError("차트 데이터를 불러오지 못했습니다.");
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [code, limit]);

  return { items, loading, error };
}
