import type { DecisionView } from "../types";

/** 판정 5단계 정렬 우선순위(강력매수=0 … 강력매도=4). 미상은 5로 뒤로 보낸다. */
export const DECISION_RANK: Record<DecisionView, number> = {
  강력매수: 0,
  매수: 1,
  관망: 2,
  매도: 3,
  강력매도: 4,
};

/** 판정 분포 집계용 0-초기화 카운트. 스프레드로 복사해 사용한다. */
export const EMPTY_DECISION_COUNTS: Record<DecisionView, number> = {
  강력매수: 0,
  매수: 0,
  관망: 0,
  매도: 0,
  강력매도: 0,
};

/** 판정 라벨 배열을 5단계 분포로 집계한다(유효 판정만 total 에 포함). */
export function countDecisions(
  views: Array<DecisionView | string | null | undefined>
): { counts: Record<DecisionView, number>; total: number } {
  const counts: Record<DecisionView, number> = { ...EMPTY_DECISION_COUNTS };
  let total = 0;
  for (const v of views) {
    if (v && v in counts) {
      counts[v as DecisionView] += 1;
      total += 1;
    }
  }
  return { counts, total };
}
