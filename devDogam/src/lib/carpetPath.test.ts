// ── carpetPath.ts 회귀 시험 (M3.2) ───────────────────────────────────────────
// §7 keyframe 타임라인 상수 합산·비율 검증.
// 실제 애니메이션은 jsdom에서 실행 불가이므로 순수 수치 로직만 검증.

import { describe, it, expect } from "vitest";
import {
  BOW_DURATION_MS,
  STEP_TO_CARPET_MS,
  CARPET_TO_STAIRS_MS,
  BOW_DOWN_MS,
  BOW_UP_MS,
  RETURN_MS,
  CARPET_STEP_X_PX,
  CARPET_CENTER_X_PX,
  CARPET_Y_PX,
  DOJE_CARPET_START_Y,
} from "@/lib/carpetPath";

describe("carpetPath — §7 keyframe 타임라인 상수", () => {
  it("BOW_DURATION_MS = 각 단계 합산 2100ms", () => {
    const total = STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS + BOW_UP_MS + RETURN_MS;
    expect(total).toBe(2100);
    expect(BOW_DURATION_MS).toBe(2100);
  });

  it("각 단계 ms 값이 시방서 §7과 일치", () => {
    expect(STEP_TO_CARPET_MS).toBe(300);
    expect(CARPET_TO_STAIRS_MS).toBe(500);
    expect(BOW_DOWN_MS).toBe(400);
    expect(BOW_UP_MS).toBe(200);
    expect(RETURN_MS).toBe(700);
  });

  it("모든 단계 ms는 양수", () => {
    expect(STEP_TO_CARPET_MS).toBeGreaterThan(0);
    expect(CARPET_TO_STAIRS_MS).toBeGreaterThan(0);
    expect(BOW_DOWN_MS).toBeGreaterThan(0);
    expect(BOW_UP_MS).toBeGreaterThan(0);
    expect(RETURN_MS).toBeGreaterThan(0);
  });
});

describe("carpetPath — keyframe times 비율 (framer-motion times[])", () => {
  // framer-motion times[] 는 [0..1] 정규화. ManagerCharacter.buildBowKeyframes와 동일 로직 검증.
  it("t1(카펫 입구) 비율이 step1/전체 와 일치", () => {
    const t1 = STEP_TO_CARPET_MS / BOW_DURATION_MS;
    expect(t1).toBeCloseTo(300 / 2100);
    expect(t1).toBeGreaterThan(0);
    expect(t1).toBeLessThan(1);
  });

  it("t2(카펫 중앙) > t1 (입구보다 나중)", () => {
    const t1 = STEP_TO_CARPET_MS / BOW_DURATION_MS;
    const t2 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS) / BOW_DURATION_MS;
    expect(t2).toBeGreaterThan(t1);
  });

  it("t3(절 최심) > t2", () => {
    const t2 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS) / BOW_DURATION_MS;
    const t3 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS) / BOW_DURATION_MS;
    expect(t3).toBeGreaterThan(t2);
  });

  it("t4(절 복귀) > t3, < 1", () => {
    const t3 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS) / BOW_DURATION_MS;
    const t4 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS + BOW_UP_MS) / BOW_DURATION_MS;
    expect(t4).toBeGreaterThan(t3);
    expect(t4).toBeLessThan(1);
  });

  it("times 배열 6개 요소 [0, t1, t2, t3, t4, 1] 단조 증가", () => {
    const t1 = STEP_TO_CARPET_MS / BOW_DURATION_MS;
    const t2 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS) / BOW_DURATION_MS;
    const t3 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS) / BOW_DURATION_MS;
    const t4 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS + BOW_UP_MS) / BOW_DURATION_MS;
    const times = [0, t1, t2, t3, t4, 1];

    for (let i = 1; i < times.length; i++) {
      expect(times[i]).toBeGreaterThan(times[i - 1]);
    }
  });
});

describe("carpetPath — 이동 좌표 상수", () => {
  it("CARPET_STEP_X_PX: 카펫 입구 x 이동, 양수 px", () => {
    expect(CARPET_STEP_X_PX).toBeGreaterThan(0);
    expect(CARPET_STEP_X_PX).toBe(80);
  });

  it("CARPET_CENTER_X_PX: 카펫 중앙(계단 앞) x, STEP보다 큼 (더 이동)", () => {
    expect(CARPET_CENTER_X_PX).toBeGreaterThan(CARPET_STEP_X_PX);
    expect(CARPET_CENTER_X_PX).toBe(160);
  });

  it("CARPET_Y_PX: 위 방향 음수 (화면 위쪽 = 임금 방향)", () => {
    expect(CARPET_Y_PX).toBeLessThan(0);
    expect(CARPET_Y_PX).toBe(-60); // v3: 매니저 top=58~76% 계단 도달 위해 -60px로 확장
  });

  it("DOJE_CARPET_START_Y: §6 '30vh' 문자열 일치", () => {
    expect(DOJE_CARPET_START_Y).toBe("30vh");
  });
});

describe("carpetPath — buildBowKeyframes 로직 (ManagerCharacter 동일 로직)", () => {
  // ManagerCharacter 내 buildBowKeyframes와 동일한 로직을 여기서 직접 검증.
  // (순수 함수 추출이 없으므로 상수를 이용한 동등 계산으로 검증)

  function buildBowKeyframes(side?: "left" | "right") {
    const stepX = side === "right"
      ? `-${CARPET_STEP_X_PX}px`
      : `${CARPET_STEP_X_PX}px`;
    const carpetX = side === "right"
      ? `-${CARPET_CENTER_X_PX}px`
      : `${CARPET_CENTER_X_PX}px`;
    const carpetY = `${CARPET_Y_PX}px`;

    const t1 = STEP_TO_CARPET_MS / BOW_DURATION_MS;
    const t2 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS) / BOW_DURATION_MS;
    const t3 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS) / BOW_DURATION_MS;
    const t4 = (STEP_TO_CARPET_MS + CARPET_TO_STAIRS_MS + BOW_DOWN_MS + BOW_UP_MS) / BOW_DURATION_MS;

    return {
      x: [0, stepX, carpetX, carpetX, carpetX, 0] as (string | number)[],
      y: [0, "0px", carpetY, carpetY, carpetY, "0px"] as (string | number)[],
      scaleY: [1, 1, 1, 0.92, 1, 1] as number[],
      rotate: [0, 0, 0, 5, 0, 0] as number[],
      transition: {
        duration: BOW_DURATION_MS / 1000,
        times: [0, t1, t2, t3, t4, 1] as number[],
        ease: "easeInOut" as const,
      },
    };
  }

  it("side=left: x[1] 양수 방향, x[2] 더 큰 양수", () => {
    const kf = buildBowKeyframes("left");
    expect(kf.x[1]).toBe(`${CARPET_STEP_X_PX}px`);
    expect(kf.x[2]).toBe(`${CARPET_CENTER_X_PX}px`);
  });

  it("side=right: x[1] 음수 방향, x[2] 더 큰 음수", () => {
    const kf = buildBowKeyframes("right");
    expect(kf.x[1]).toBe(`-${CARPET_STEP_X_PX}px`);
    expect(kf.x[2]).toBe(`-${CARPET_CENTER_X_PX}px`);
  });

  it("side 미지정(undefined): left와 동일 방향", () => {
    const kf = buildBowKeyframes(undefined);
    expect(kf.x[1]).toBe(`${CARPET_STEP_X_PX}px`);
  });

  it("y 시작(0)·끝(0) — 자기 자리 복귀", () => {
    const kf = buildBowKeyframes("left");
    expect(kf.y[0]).toBe(0);
    expect(kf.y[5]).toBe("0px");
  });

  it("y[2..4] = carpetY — 계단 앞 도달 후 x만 이동", () => {
    const kf = buildBowKeyframes("left");
    const carpetY = `${CARPET_Y_PX}px`;
    expect(kf.y[2]).toBe(carpetY);
    expect(kf.y[3]).toBe(carpetY);
    expect(kf.y[4]).toBe(carpetY);
  });

  it("절 최심 scaleY: [1,1,1, 0.92, 1,1]", () => {
    const kf = buildBowKeyframes("left");
    expect(kf.scaleY).toEqual([1, 1, 1, 0.92, 1, 1]);
  });

  it("절 최심 rotate: [0,0,0, 5, 0,0]", () => {
    const kf = buildBowKeyframes("left");
    expect(kf.rotate).toEqual([0, 0, 0, 5, 0, 0]);
  });

  it("transition.duration = BOW_DURATION_MS/1000 (초 단위)", () => {
    const kf = buildBowKeyframes("left");
    expect(kf.transition.duration).toBe(BOW_DURATION_MS / 1000);
    expect(kf.transition.duration).toBe(2.1);
  });

  it("transition.times 6개 요소, 단조 증가, [0..1] 범위", () => {
    const kf = buildBowKeyframes("left");
    const times = kf.transition.times;
    expect(times).toHaveLength(6);
    expect(times[0]).toBe(0);
    expect(times[5]).toBe(1);
    for (let i = 1; i < times.length; i++) {
      expect(times[i]).toBeGreaterThan(times[i - 1]);
    }
  });

  it("keyframe 배열 길이 모두 6 (times와 동일)", () => {
    const kf = buildBowKeyframes("left");
    expect(kf.x).toHaveLength(6);
    expect(kf.y).toHaveLength(6);
    expect(kf.scaleY).toHaveLength(6);
    expect(kf.rotate).toHaveLength(6);
  });
});
