import { describe, expect, it } from "vitest";
import type { SnapshotFactors } from "../types";
import {
  DECISION_RANK,
  EMPTY_DECISION_COUNTS,
  MIN_BARS_60M,
  countDecisions,
  isShortViewWarming,
} from "./decision";

/** 테스트에 필요한 필드만 채운 factors — 나머지는 판정 표시에 쓰이지 않는다. */
function factors(bars: number | null | undefined): SnapshotFactors {
  return { bars_60m: bars } as unknown as SnapshotFactors;
}

describe("isShortViewWarming", () => {
  it("60분봉이 최소 봉수에 못 미치면 워밍업으로 본다", () => {
    // 이 구간에서 백엔드는 '데이터부족'이 아니라 0점=관망을 낸다 —
    // 화면이 그 사실을 구분하지 못하면 사용자가 '관망'을 시장 판단으로 읽는다.
    expect(isShortViewWarming(factors(MIN_BARS_60M - 1))).toBe(true);
    expect(isShortViewWarming(factors(0))).toBe(true);
  });

  it("최소 봉수를 채우면 워밍업이 아니다(경계 포함)", () => {
    expect(isShortViewWarming(factors(MIN_BARS_60M))).toBe(false);
    expect(isShortViewWarming(factors(MIN_BARS_60M + 100))).toBe(false);
  });

  it("bars_60m 이 없는 구버전 응답은 기존 동작을 유지한다", () => {
    expect(isShortViewWarming(factors(undefined))).toBe(false);
    expect(isShortViewWarming(factors(null))).toBe(false);
    expect(isShortViewWarming(null)).toBe(false);
    expect(isShortViewWarming(undefined)).toBe(false);
  });

  it("백엔드 최소 봉수(MACD 35봉)와 같은 값을 쓴다", () => {
    // 이 상수가 갈리면 화면과 판정이 서로 다른 기준을 보게 된다.
    expect(MIN_BARS_60M).toBe(35);
  });
});

describe("countDecisions", () => {
  it("5단계만 세고 '데이터부족'·null 은 total 에서 제외한다", () => {
    const { counts, total } = countDecisions([
      "강력매수", "매수", "매수", "관망", "매도", "데이터부족", null, undefined,
    ]);
    expect(total).toBe(5);
    expect(counts.강력매수).toBe(1);
    expect(counts.매수).toBe(2);
    expect(counts.관망).toBe(1);
    expect(counts.매도).toBe(1);
    expect(counts.강력매도).toBe(0);
  });

  it("알 수 없는 문자열도 무시한다(구버전·오타 방어)", () => {
    expect(countDecisions(["중립", "BUY"]).total).toBe(0);
  });

  it("빈 입력은 0으로 채운 분포를 준다", () => {
    const { counts, total } = countDecisions([]);
    expect(total).toBe(0);
    expect(counts).toEqual(EMPTY_DECISION_COUNTS);
  });

  it("호출해도 EMPTY_DECISION_COUNTS 원본이 오염되지 않는다", () => {
    countDecisions(["매수", "매수"]);
    expect(EMPTY_DECISION_COUNTS.매수).toBe(0);
  });
});

describe("DECISION_RANK", () => {
  it("강력매수 → 강력매도 순으로 정렬된다", () => {
    const sorted = (["관망", "강력매도", "강력매수", "매도", "매수"] as const)
      .slice()
      .sort((a, b) => DECISION_RANK[a] - DECISION_RANK[b]);
    expect(sorted).toEqual(["강력매수", "매수", "관망", "매도", "강력매도"]);
  });
});
