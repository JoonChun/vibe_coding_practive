// ── 도제 동선·배치 회귀 시험 (M3.1-1·4, v3 추가) ────────────────────────────
// DojeCharacter는 framer-motion initial/animate를 통해 동선을 구현.
// jsdom 없이 순수 로직 검증: DOJE_CARPET_START_Y 상수,
// dojeBubbles prop 연결 로직, DojeFloorRow 레이아웃 정합성.

import { describe, it, expect } from "vitest";
import { DOJE_CARPET_START_Y } from "@/lib/carpetPath";
import { CHARACTERS } from "@/lib/characters";

// ── ManagerCharacter의 dojeBubbles 연결 로직 검증 헬퍼 ───────────────────────
// 각 visibleDoje에 dojeBubbles[dojeKey]를 연결하는 것이 올바른지 검증.
function resolveDojeBubbles(
  visibleDojes: string[],
  dojeBubbles: Record<string, string>
): Array<{ dojeKey: string; message: string | undefined }> {
  return visibleDojes.map((dojeKey) => ({
    dojeKey,
    message: dojeBubbles[dojeKey],
  }));
}

// ── 테스트 ────────────────────────────────────────────────────────────────────

describe("DOJE_CARPET_START_Y — §6 초기 y 위치 (M3.1-1)", () => {
  it("DOJE_CARPET_START_Y === '30vh'", () => {
    expect(DOJE_CARPET_START_Y).toBe("30vh");
  });

  it("문자열 타입", () => {
    expect(typeof DOJE_CARPET_START_Y).toBe("string");
  });
});

describe("DojeFloorRow 레이아웃 정합성 (v3 M3.1-5)", () => {
  // DOJE_FLOOR_LAYOUT과 동일한 상수 — 소스 변경 시 이 테스트도 업데이트 필요
  const DOJE_FLOOR_LAYOUT = [
    { name: "planning-hojo",       left: "6%",  top: "92%" },
    { name: "uiux-hwawon",         left: "15%", top: "92%" },
    { name: "docs-sagwan",         left: "24%", top: "92%" },
    { name: "research-jeja",       left: "33%", top: "92%" },
    { name: "visual-hwagong",      left: "42%", top: "92%" },
    { name: "security-chukhu",     left: "58%", top: "92%" },
    { name: "perf-uiwon",          left: "64%", top: "92%" },
    { name: "test-gungwan",        left: "70%", top: "92%" },
    { name: "frontend-dancheong",  left: "76%", top: "92%" },
    { name: "backend-gigwan",      left: "82%", top: "92%" },
    { name: "infra-tomok",         left: "88%", top: "92%" },
    { name: "integration-tongsin", left: "94%", top: "92%" },
  ] as const;

  it("도제 12명 전원 레이아웃에 포함", () => {
    expect(DOJE_FLOOR_LAYOUT).toHaveLength(12);
  });

  it("모든 도제 이름이 CHARACTERS에 존재", () => {
    for (const d of DOJE_FLOOR_LAYOUT) {
      expect(CHARACTERS[d.name], `${d.name} CHARACTERS 미등록`).toBeDefined();
    }
  });

  it("모든 도제가 manager=false (진짜 도제만 배치)", () => {
    for (const d of DOJE_FLOOR_LAYOUT) {
      expect(CHARACTERS[d.name]?.manager, `${d.name}이 매니저임`).toBe(false);
    }
  });

  it("좌측 5명(6~42%) + 우측 7명(58~94%) 카펫 중앙 비움 확인", () => {
    const leftDojes = DOJE_FLOOR_LAYOUT.filter((d) => {
      const pct = parseInt(d.left);
      return pct <= 42;
    });
    const rightDojes = DOJE_FLOOR_LAYOUT.filter((d) => {
      const pct = parseInt(d.left);
      return pct >= 58;
    });
    expect(leftDojes).toHaveLength(5);
    expect(rightDojes).toHaveLength(7);
  });

  it("모든 도제 top=92% (마룻바닥 일렬)", () => {
    for (const d of DOJE_FLOOR_LAYOUT) {
      expect(d.top).toBe("92%");
    }
  });
});

describe("dojeBubbles prop 연결 (M3.1-4) — 각 도제에 메시지 올바르게 매핑", () => {
  it("dojeBubbles에 도제 키 있으면 message 전달", () => {
    const visibleDojes = ["planning-hojo", "uiux-hwawon"];
    const dojeBubbles = {
      "planning-hojo": "일정 검토 중",
      "uiux-hwawon": "화면 설계 완료",
    };
    const result = resolveDojeBubbles(visibleDojes, dojeBubbles);
    expect(result[0]).toEqual({ dojeKey: "planning-hojo", message: "일정 검토 중" });
    expect(result[1]).toEqual({ dojeKey: "uiux-hwawon", message: "화면 설계 완료" });
  });

  it("dojeBubbles에 도제 키 없으면 message undefined", () => {
    const visibleDojes = ["planning-hojo"];
    const dojeBubbles = {}; // 빈 map
    const result = resolveDojeBubbles(visibleDojes, dojeBubbles);
    expect(result[0].message).toBeUndefined();
  });

  it("visibleDojes 빈 배열이면 결과도 빈 배열", () => {
    const result = resolveDojeBubbles([], { "planning-hojo": "메시지" });
    expect(result).toHaveLength(0);
  });

  it("dojeBubbles에 visibleDoje 외 매니저 메시지 있어도 무시됨", () => {
    const visibleDojes = ["planning-hojo"];
    const dojeBubbles = {
      "planning-hojo": "도제 메시지",
      "planner-dojeon": "매니저 메시지", // 매니저는 visibleDojes에 없음
    };
    const result = resolveDojeBubbles(visibleDojes, dojeBubbles);
    expect(result).toHaveLength(1);
    expect(result[0].message).toBe("도제 메시지");
  });

  it("동일 매니저 소속 도제 3명 — 각각 다른 메시지 독립 전달", () => {
    // planner-dojeon 소속 도제 3인
    const plannerDojes = ["planning-hojo", "uiux-hwawon", "docs-sagwan"];
    const dojeBubbles = {
      "planning-hojo": "일정 수립",
      "uiux-hwawon":   "화면 초안",
      "docs-sagwan":   "문서 작성 중",
    };
    const result = resolveDojeBubbles(plannerDojes, dojeBubbles);
    result.forEach((r, idx) => {
      expect(r.message).toBe(dojeBubbles[plannerDojes[idx] as keyof typeof dojeBubbles]);
    });
  });
});

describe("CHARACTERS — 도제 parent 정합성 회귀 (M3.1 전제)", () => {
  it("모든 도제에 parent 필드가 존재하고 유효한 매니저 이름", () => {
    const managerNames = new Set(
      Object.values(CHARACTERS)
        .filter((c) => c.manager && c.name !== "king")
        .map((c) => c.name)
    );
    const dojes = Object.values(CHARACTERS).filter((c) => !c.manager && c.name !== "king");
    for (const doje of dojes) {
      expect(doje.parent, `${doje.name} parent 미설정`).toBeDefined();
      expect(managerNames.has(doje.parent!), `${doje.name}.parent=${doje.parent} 유효하지 않음`).toBe(true);
    }
  });

  it("implementer-yeongsil 소속 도제 4인 — 단청·기관·토목·통신", () => {
    const expected = ["frontend-dancheong", "backend-gigwan", "infra-tomok", "integration-tongsin"];
    const actual = Object.values(CHARACTERS)
      .filter((c) => c.parent === "implementer-yeongsil")
      .map((c) => c.name);
    for (const name of expected) {
      expect(actual).toContain(name);
    }
  });

  it("planner-dojeon 소속 도제 3인 — 호조낭청·화원·사관", () => {
    const expected = ["planning-hojo", "uiux-hwawon", "docs-sagwan"];
    const actual = Object.values(CHARACTERS)
      .filter((c) => c.parent === "planner-dojeon")
      .map((c) => c.name);
    for (const name of expected) {
      expect(actual).toContain(name);
    }
  });
});

describe("bowTrigger — mount 시 최초 절 방지 로직 (M3.2-3 ref 패턴 검증)", () => {
  // ManagerCharacter useEffect의 prevTriggerRef 패턴을 순수 함수로 재현하여 검증.
  // 실제 useRef는 jsdom 없이 테스트 불가이므로, 동일한 분기 로직을 순수 함수로 검증.

  function shouldBow(
    prevTrigger: string | undefined,
    newTrigger: string | undefined
  ): "skip_mount" | "skip_same" | "skip_empty" | "bow" {
    // mount 최초 실행: prevTrigger가 undefined
    if (prevTrigger === undefined) return "skip_mount";
    // 값 변화 없음
    if (newTrigger === prevTrigger) return "skip_same";
    // 빈 값
    if (!newTrigger) return "skip_empty";
    return "bow";
  }

  it("mount 시 (prevTrigger=undefined) → skip_mount (절 X)", () => {
    expect(shouldBow(undefined, "evt-1")).toBe("skip_mount");
  });

  it("mount 시 bowTrigger도 undefined → skip_mount", () => {
    expect(shouldBow(undefined, undefined)).toBe("skip_mount");
  });

  it("같은 값 두 번 전달 → skip_same (절 X)", () => {
    expect(shouldBow("evt-1", "evt-1")).toBe("skip_same");
  });

  it("빈 문자열 전달 → skip_empty (절 X)", () => {
    expect(shouldBow("evt-1", "")).toBe("skip_empty");
  });

  it("값이 바뀌면 → bow (절 발동)", () => {
    expect(shouldBow("evt-1", "evt-2")).toBe("bow");
  });

  it("undefined → 실제 id로 변경 시 → bow (절 발동)", () => {
    // prevTriggerRef에 이미 undefined가 아닌 값 기록된 후
    expect(shouldBow("", "evt-1")).toBe("bow");
  });
});
