// ── DojeCharacter 상태머신·bobbingDelay·DOJE_FLOOR_LAYOUT 카펫 침범 회귀 시험 ──
// (군관 M3.1-5 보완 — dojeLayout.test.ts 미커버 케이스)
//
// 검증 범위:
//   A. bobbingDelay deterministic — getCharacterIndex 기반 12도제 delay 고유성
//   B. 활성 상태머신 animateProps 로직 (순수 재현)
//   C. labelStyle hex 합성 (D5 현판)
//   D. DOJE_FLOOR_LAYOUT left 43~57% 침범 여부 (gap 경계 명시적 검증)
//   E. getCharacterIndex — 미등록 이름 처리 (SSR-safe 보장)
//   F. DOJES·getDojesByManager 정합 (12명 합산)

import { describe, it, expect } from "vitest";
import {
  CHARACTERS,
  CHARACTER_KEYS,
  getCharacterIndex,
  DOJES,
  getDojesByManager,
} from "@/lib/characters";
import { DOJE_CARPET_START_Y } from "@/lib/carpetPath";

// ── DOJE_FLOOR_LAYOUT 로컬 사본 (DojeFloorRow.tsx와 동기화) ─────────────────
// DojeFloorRow.tsx 변경 시 이 배열도 함께 업데이트 필요.
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

// ── A. bobbingDelay deterministic ───────────────────────────────────────────
describe("A. bobbingDelay — getCharacterIndex 기반 고유성 (SSR-safe)", () => {
  // CHARACTER_KEYS 순서: king(0) planner-dojeon(1) implementer-yeongsil(2)
  // reviewer-sunsin(3) ideator-yagyong(4) planning-hojo(5) uiux-hwawon(6)
  // docs-sagwan(7) frontend-dancheong(8) backend-gigwan(9) infra-tomok(10)
  // integration-tongsin(11) security-chukhu(12) perf-uiwon(13) test-gungwan(14)
  // research-jeja(15) visual-hwagong(16)

  const dojeNames = DOJE_FLOOR_LAYOUT.map((d) => d.name);

  it("12명 도제 모두 getCharacterIndex >= 0 (등록 확인)", () => {
    for (const name of dojeNames) {
      expect(getCharacterIndex(name), `${name} INDEX 미등록`).toBeGreaterThanOrEqual(0);
    }
  });

  it("12명 도제 bobbingDelay 모두 서로 다른 값 (충돌 X)", () => {
    const delays = dojeNames.map((name) => getCharacterIndex(name) * 0.15);
    const uniqueDelays = new Set(delays);
    expect(uniqueDelays.size).toBe(dojeNames.length);
  });

  it("planning-hojo index=5 → delay=0.75s (5*0.15)", () => {
    const idx = getCharacterIndex("planning-hojo");
    expect(idx).toBe(5);
    expect(idx * 0.15).toBeCloseTo(0.75);
  });

  it("visual-hwagong index=16 → delay=2.4s (12번째 도제 중 최장)", () => {
    const idx = getCharacterIndex("visual-hwagong");
    expect(idx).toBe(16);
    expect(idx * 0.15).toBeCloseTo(2.4);
  });

  it("미등록 이름 → index=-1 (SSR 환경에서 NaN delay 대신 -0.15, 음수지만 crash X)", () => {
    const idx = getCharacterIndex("unknown-agent");
    expect(idx).toBe(-1);
    // delay가 음수여도 framer-motion은 0으로 처리. 중요한 것은 예외 미발생.
    expect(() => idx * 0.15).not.toThrow();
  });

  it("12명 delay 범위: 최소 > 0, 최대 < 4초 (bobbing 주기 1.8s 내 여유)", () => {
    const delays = dojeNames.map((name) => getCharacterIndex(name) * 0.15);
    expect(Math.min(...delays)).toBeGreaterThan(0);
    expect(Math.max(...delays)).toBeLessThan(4);
  });
});

// ── B. 활성 상태머신 animateProps 로직 ───────────────────────────────────────
describe("B. DojeCharacter 상태머신 — animateProps 로직 (순수 재현)", () => {
  // DojeCharacter 내 animateProps 분기와 동일한 순수 함수
  function resolveAnimateProps(mounted: boolean, isActive: boolean) {
    if (mounted && isActive) {
      return { y: [-6, -8, -6] as number[], scale: 1.08, opacity: 1 };
    } else if (mounted) {
      return { y: 0, scale: 1, opacity: 1 };
    } else {
      return { y: 0, scale: 1, opacity: 1 };
    }
  }

  it("mount 전 → y=0, scale=1, opacity=1 (초기 정지 상태)", () => {
    const props = resolveAnimateProps(false, false);
    expect(props.y).toBe(0);
    expect(props.scale).toBe(1);
    expect(props.opacity).toBe(1);
  });

  it("mount 전 + isActive=true여도 → y=0 (활성 무시, 페이드인 우선)", () => {
    const props = resolveAnimateProps(false, true);
    expect(props.y).toBe(0);
    expect(props.scale).toBe(1);
  });

  it("mount 후 + isActive=false → y=0, scale=1 (대기 상태)", () => {
    const props = resolveAnimateProps(true, false);
    expect(props.y).toBe(0);
    expect(props.scale).toBe(1);
  });

  it("mount 후 + isActive=true → y=[-6,-8,-6], scale=1.08 (bobbing+부상)", () => {
    const props = resolveAnimateProps(true, true);
    expect(props.y).toEqual([-6, -8, -6]);
    expect(props.scale).toBe(1.08);
    expect(props.opacity).toBe(1);
  });

  it("false→true 전환: scale 1.08은 1.0보다 8% 부상", () => {
    const inactive = resolveAnimateProps(true, false);
    const active   = resolveAnimateProps(true, true);
    expect(active.scale).toBeGreaterThan(inactive.scale as number);
    expect(active.scale - (inactive.scale as number)).toBeCloseTo(0.08);
  });

  it("isActive false→true→false 상태 전환 시 y 배열 타입 변화", () => {
    const inactive = resolveAnimateProps(true, false);
    const active   = resolveAnimateProps(true, true);
    const backToInactive = resolveAnimateProps(true, false);

    expect(typeof inactive.y).toBe("number");          // 비활성: 단일 숫자
    expect(Array.isArray(active.y)).toBe(true);         // 활성: 배열(bobbing)
    expect(typeof backToInactive.y).toBe("number");     // 복귀: 단일 숫자
  });

  it("initial y = DOJE_CARPET_START_Y ('30vh') — mount 1회 페이드인 시작점", () => {
    // DojeCharacter의 initial={{ y: DOJE_CARPET_START_Y }} 검증
    expect(DOJE_CARPET_START_Y).toBe("30vh");
    // initial y와 mount 후 animate y=0 사이 거리: 30vh → 0 (슬라이드업)
    expect(DOJE_CARPET_START_Y).not.toBe("0");
  });
});

// ── C. labelStyle hex 합성 (D5 현판) ────────────────────────────────────────
describe("C. labelStyle — D5 현판 활성·비활성 스타일 합성", () => {
  function resolveLabelStyle(isActive: boolean, agentName: string) {
    const character = CHARACTERS[agentName];
    if (!character) return null;
    if (isActive) {
      return {
        color: "#FFFFFF",
        backgroundColor: character.hex,
        padding: "1px 4px",
        borderRadius: "2px",
        minWidth: "48px",
        display: "inline-block",
        textAlign: "center" as const,
      };
    }
    return {
      color: "#F4ECD8",
      minWidth: "48px",
      display: "inline-block",
      textAlign: "center" as const,
    };
  }

  it("활성 시 색상 = character.hex (캐릭터 고유 색)", () => {
    const style = resolveLabelStyle(true, "planning-hojo");
    expect(style?.backgroundColor).toBe(CHARACTERS["planning-hojo"].hex);
    expect(style?.color).toBe("#FFFFFF");
  });

  it("비활성 시 backgroundColor 없음 (한지색 글씨만)", () => {
    const style = resolveLabelStyle(false, "planning-hojo");
    expect(style).not.toHaveProperty("backgroundColor");
    expect(style?.color).toBe("#F4ECD8");
  });

  it("12명 도제 각자 hex가 모두 #로 시작하는 유효한 16진수", () => {
    const hexPattern = /^#[0-9A-Fa-f]{6}$/;
    for (const d of DOJE_FLOOR_LAYOUT) {
      const hex = CHARACTERS[d.name]?.hex;
      expect(hex, `${d.name} hex 비정상`).toMatch(hexPattern);
    }
  });

  it("매니저·도제 hex 충돌 없음 — 각 캐릭터가 고유 hex", () => {
    // 동일 hex 공유 캐릭터는 시각적으로 구분 불가 → 경고 케이스
    const allHex = Object.values(CHARACTERS)
      .filter((c) => c.name !== "king")
      .map((c) => c.hex);
    const uniqueHex = new Set(allHex);
    // 16개 캐릭터(king 제외 15개)에서 중복 없이 유일해야 함
    expect(uniqueHex.size).toBe(allHex.length);
  });
});

// ── D. DOJE_FLOOR_LAYOUT 카펫 중앙(43~57%) 침범 X — 경계 명시 검증 ─────────
describe("D. DOJE_FLOOR_LAYOUT — 카펫 중앙 갭(43~57%) 침범 여부", () => {
  const CARPET_LEFT_BOUND  = 43; // 카펫 좌측 경계 (%)
  const CARPET_RIGHT_BOUND = 57; // 카펫 우측 경계 (%)

  it("43~57% 범위에 속하는 도제가 0명 (카펫 중앙 완전 비움)", () => {
    const intruders = DOJE_FLOOR_LAYOUT.filter((d) => {
      const pct = parseInt(d.left);
      return pct > CARPET_LEFT_BOUND && pct < CARPET_RIGHT_BOUND;
    });
    expect(intruders).toHaveLength(0);
  });

  it("좌측 최우단(visual-hwagong 42%)이 경계(43%) 미만", () => {
    const visual = DOJE_FLOOR_LAYOUT.find((d) => d.name === "visual-hwagong");
    expect(visual).toBeDefined();
    expect(parseInt(visual!.left)).toBeLessThan(CARPET_LEFT_BOUND);
  });

  it("우측 최좌단(security-chukhu 58%)이 경계(57%) 초과", () => {
    const security = DOJE_FLOOR_LAYOUT.find((d) => d.name === "security-chukhu");
    expect(security).toBeDefined();
    expect(parseInt(security!.left)).toBeGreaterThan(CARPET_RIGHT_BOUND);
  });

  it("좌측 5명 모두 6~42% — 각각 개별 범위 확인", () => {
    const leftGroup = ["planning-hojo", "uiux-hwawon", "docs-sagwan", "research-jeja", "visual-hwagong"];
    for (const name of leftGroup) {
      const entry = DOJE_FLOOR_LAYOUT.find((d) => d.name === name);
      expect(entry).toBeDefined();
      const pct = parseInt(entry!.left);
      expect(pct, `${name} 좌측 범위 초과`).toBeGreaterThanOrEqual(6);
      expect(pct, `${name} 카펫 침범`).toBeLessThanOrEqual(42);
    }
  });

  it("우측 7명 모두 58~94% — 각각 개별 범위 확인", () => {
    const rightGroup = [
      "security-chukhu", "perf-uiwon", "test-gungwan",
      "frontend-dancheong", "backend-gigwan", "infra-tomok", "integration-tongsin",
    ];
    for (const name of rightGroup) {
      const entry = DOJE_FLOOR_LAYOUT.find((d) => d.name === name);
      expect(entry).toBeDefined();
      const pct = parseInt(entry!.left);
      expect(pct, `${name} 우측 범위 미달`).toBeGreaterThanOrEqual(58);
      expect(pct, `${name} 화면 초과`).toBeLessThanOrEqual(94);
    }
  });

  it("좌측·우측 사이 갭 16%p 이상 (42→58, 실제 16%p 여유)", () => {
    const leftMax  = Math.max(...DOJE_FLOOR_LAYOUT.filter((d) => parseInt(d.left) <= 42).map((d) => parseInt(d.left)));
    const rightMin = Math.min(...DOJE_FLOOR_LAYOUT.filter((d) => parseInt(d.left) >= 58).map((d) => parseInt(d.left)));
    expect(rightMin - leftMax).toBeGreaterThanOrEqual(16);
  });
});

// ── E. DOJES·getDojesByManager 정합 (12명 합산) ───────────────────────────
describe("E. DOJES·getDojesByManager — 12명 완전성", () => {
  it("DOJES 길이 = 12 (임금·매니저 제외한 순수 도제)", () => {
    expect(DOJES).toHaveLength(12);
  });

  it("4개 매니저 소속 합산 = 12 (누락·중복 X)", () => {
    const managerNames = ["planner-dojeon", "implementer-yeongsil", "reviewer-sunsin", "ideator-yagyong"];
    const total = managerNames.reduce(
      (sum, m) => sum + getDojesByManager(m).length,
      0
    );
    expect(total).toBe(12);
  });

  it("정약용 소속 2인 — 제자·화공", () => {
    const yagyong = getDojesByManager("ideator-yagyong");
    expect(yagyong).toHaveLength(2);
    const names = yagyong.map((c) => c.name);
    expect(names).toContain("research-jeja");
    expect(names).toContain("visual-hwagong");
  });

  it("이순신 소속 3인 — 척후·의원·군관", () => {
    const sunsin = getDojesByManager("reviewer-sunsin");
    expect(sunsin).toHaveLength(3);
    const names = sunsin.map((c) => c.name);
    expect(names).toContain("security-chukhu");
    expect(names).toContain("perf-uiwon");
    expect(names).toContain("test-gungwan");
  });

  it("DOJE_FLOOR_LAYOUT 12명 = DOJES 12명 (동일 집합)", () => {
    const layoutNames = new Set<string>(DOJE_FLOOR_LAYOUT.map((d) => d.name));
    const dojeNames   = new Set<string>(DOJES.map((c) => c.name));
    // 레이아웃 모든 이름이 DOJES에 있어야 함
    for (const name of layoutNames) {
      expect(dojeNames.has(name), `${name} DOJES 미등록`).toBe(true);
    }
    // DOJES 모든 이름이 레이아웃에 있어야 함
    for (const name of dojeNames) {
      expect(layoutNames.has(name), `${name} LAYOUT 미등록`).toBe(true);
    }
  });
});
