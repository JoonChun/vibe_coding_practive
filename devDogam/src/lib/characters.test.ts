// ── characters.ts king 메타 회귀 시험 ─────────────────────────────────────────
// β++ 시각 재설계 이후 CHARACTER_KEYS 수·king 위치·MANAGERS·DOJES 정합성 확인

import { describe, it, expect } from "vitest";
import {
  CHARACTERS,
  MANAGERS,
  DOJES,
  CHARACTER_KEYS,
} from "./characters";

describe("characters — king 메타 회귀", () => {
  it("CHARACTERS['king'] 존재", () => {
    expect(CHARACTERS["king"]).toBeDefined();
  });

  it("CHARACTERS['king'].manager === false", () => {
    expect(CHARACTERS["king"].manager).toBe(false);
  });

  it("MANAGERS 배열에 king 없음", () => {
    expect(MANAGERS.some((c) => c.name === "king")).toBe(false);
  });

  it("DOJES 배열에 king 없음", () => {
    expect(DOJES.some((c) => c.name === "king")).toBe(false);
  });

  it("CHARACTER_KEYS 총 17개 (king + 매니저4 + 도제12)", () => {
    expect(CHARACTER_KEYS.length).toBe(17);
  });

  it("MANAGERS는 정확히 4인", () => {
    expect(MANAGERS).toHaveLength(4);
  });

  it("DOJES는 12인 (17 - king 1 - 매니저 4)", () => {
    expect(DOJES).toHaveLength(12);
  });
});
