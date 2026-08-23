import type { DecisionView, SnapshotFactors } from "../types";

/**
 * 단기 판정(60분봉 MACD+RSI)에 필요한 최소 봉 수. 백엔드 collector.MIN_BARS_60M 과
 * 같은 값이며, 판정 자체는 백엔드가 계산한다 — 여기서는 "그 판정을 아직 믿을 수
 * 없다"는 표시 여부만 정한다.
 */
export const MIN_BARS_60M = 35;

/**
 * 단기 판정이 봉 부족 구간인가.
 *
 * 봉이 모자라면 MACD 는 데이터부족이지만 RSI(15봉)는 '중립'을 내므로, 합계 0점 =
 * **'관망'** 이 나온다. 사용자는 이걸 시장 판단으로 읽지만 실제로는 데이터가 없는
 * 것이고, 35번째 봉이 쌓이는 순간 가짜 '관망→매수' 전환이 생긴다.
 * bars_60m 이 없는 구버전 응답에서는 false(기존 동작 유지).
 */
export function isShortViewWarming(
  factors: SnapshotFactors | null | undefined
): boolean {
  const bars = factors?.bars_60m;
  return typeof bars === "number" && bars < MIN_BARS_60M;
}

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
