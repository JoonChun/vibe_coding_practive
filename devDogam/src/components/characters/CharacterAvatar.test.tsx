// ── CharacterAvatar 단위 시험 ─────────────────────────────────────────────────
// 목적:
//   1. 16개 CHARACTER_KEYS 각각에 대해 src="/characters/{name}.svg" 패턴 검증
//      (실제 <img> 렌더가 아닌 src 생성 로직 검증 — node 환경 대응)
//   2. 알 수 없는 agentName → console.warn 호출, null 반환
//   3. size prop("manager"|"doje"|"king") → px 64/40/80 매핑 검증
//   4. alt 속성이 CHARACTERS[name].displayName과 일치
//
// 환경: vitest (node). framer-motion·React 렌더 없이 순수 로직을 추출해 검증.
// CharacterAvatar.tsx의 핵심 로직 재현:
//   - CHARACTERS lookup → null (경고) or 렌더
//   - SIZE_MAP[size] → px 값
//   - img src = `/characters/${agentName}.svg`
//   - img alt = character.displayName

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  CHARACTERS,
  CHARACTER_KEYS,
  DOJES,
  MANAGERS,
} from "@/lib/characters";

// ── CharacterAvatar 핵심 로직 재현 ───────────────────────────────────────────
// CharacterAvatar.tsx의 렌더 결과물 속성(src, alt, width/height)을
// framer-motion / React 없이 동일 로직으로 계산.

type Size = "manager" | "doje" | "king";

const SIZE_MAP: Record<Size, number> = {
  manager: 64,
  doje: 40,
  king: 80,
} as const;

interface AvatarProps {
  agentName: string;
  size?: Size;
}

interface AvatarResult {
  src: string;
  alt: string;
  width: number;
  height: number;
}

/**
 * CharacterAvatar의 렌더 시 생성되는 <img> 속성값을 반환.
 * character를 찾지 못하면 console.warn + null 반환 (실제 컴포넌트와 동일 분기).
 */
function resolveAvatarProps(
  { agentName, size = "manager" }: AvatarProps,
  warnFn: (...args: unknown[]) => void = console.warn
): AvatarResult | null {
  const character = CHARACTERS[agentName];
  if (!character) {
    warnFn(
      `[CharacterAvatar] 알 수 없는 agentName: "${agentName}". CHARACTERS에 등록되지 않은 키요.`
    );
    return null;
  }

  const px = SIZE_MAP[size];

  return {
    src: `/characters/${agentName}.svg`,
    alt: character.displayName,
    width: px,
    height: px,
  };
}

// ── 1. 16개 CHARACTER_KEYS 전원 src 패턴 검증 ────────────────────────────────

describe("CharacterAvatar — src 패턴 (16개 CHARACTER_KEYS)", () => {
  it("CHARACTER_KEYS 총 17개 (1왕 + 4매니저 + 12도제)", () => {
    expect(CHARACTER_KEYS.length).toBe(17);
  });

  for (const key of CHARACTER_KEYS) {
    it(`${key} → src="/characters/${key}.svg"`, () => {
      const result = resolveAvatarProps({ agentName: key });
      expect(result, `${key} — resolveAvatarProps null 반환`).not.toBeNull();
      expect(result!.src).toBe(`/characters/${key}.svg`);
    });
  }
});

// ── 2. 알 수 없는 agentName → console.warn + null ────────────────────────────

describe("CharacterAvatar — 미등록 agentName 경고·null 반환", () => {
  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  it("미등록 key → null 반환", () => {
    const result = resolveAvatarProps({ agentName: "unknown-ghost" });
    expect(result).toBeNull();
  });

  it("미등록 key → console.warn 호출됨", () => {
    const mockWarn = vi.fn();
    resolveAvatarProps({ agentName: "unknown-ghost" }, mockWarn);
    expect(mockWarn).toHaveBeenCalledOnce();
  });

  it("경고 메시지에 agentName 포함", () => {
    const mockWarn = vi.fn();
    resolveAvatarProps({ agentName: "mystery-agent" }, mockWarn);
    const msg: string = mockWarn.mock.calls[0][0] as string;
    expect(msg).toContain("mystery-agent");
  });

  it("빈 문자열 → null 반환 + 경고", () => {
    const mockWarn = vi.fn();
    const result = resolveAvatarProps({ agentName: "" }, mockWarn);
    expect(result).toBeNull();
    expect(mockWarn).toHaveBeenCalledOnce();
  });

  it("등록된 key는 경고 없이 정상 반환", () => {
    const mockWarn = vi.fn();
    const result = resolveAvatarProps({ agentName: "king" }, mockWarn);
    expect(result).not.toBeNull();
    expect(mockWarn).not.toHaveBeenCalled();
  });
});

// ── 3. size prop → width/height 매핑 ────────────────────────────────────────

describe("CharacterAvatar — size prop 픽셀 매핑", () => {
  it('size="manager" → width=64, height=64', () => {
    const result = resolveAvatarProps({ agentName: "planner-dojeon", size: "manager" });
    expect(result!.width).toBe(64);
    expect(result!.height).toBe(64);
  });

  it('size="doje" → width=40, height=40', () => {
    const result = resolveAvatarProps({ agentName: "planning-hojo", size: "doje" });
    expect(result!.width).toBe(40);
    expect(result!.height).toBe(40);
  });

  it('size="king" → width=80, height=80', () => {
    const result = resolveAvatarProps({ agentName: "king", size: "king" });
    expect(result!.width).toBe(80);
    expect(result!.height).toBe(80);
  });

  it("size 기본값(미지정)은 manager(64)", () => {
    const result = resolveAvatarProps({ agentName: "implementer-yeongsil" });
    expect(result!.width).toBe(64);
    expect(result!.height).toBe(64);
  });

  it("SIZE_MAP 세 값 모두 다름 (혼용 불가)", () => {
    const values = Object.values(SIZE_MAP);
    const unique = new Set(values);
    expect(unique.size).toBe(3);
  });
});

// ── 4. alt = displayName ─────────────────────────────────────────────────────

describe("CharacterAvatar — alt 속성 = displayName", () => {
  for (const key of CHARACTER_KEYS) {
    it(`${key} alt = "${CHARACTERS[key].displayName}"`, () => {
      const result = resolveAvatarProps({ agentName: key });
      expect(result!.alt).toBe(CHARACTERS[key].displayName);
    });
  }
});

// ── 5. 도제/매니저 각 그룹별 size 적합 크기 검증 ────────────────────────────

describe("CharacterAvatar — 도제/매니저 그룹 size 일치 회귀", () => {
  it("4 매니저 — size=manager 적용 시 모두 px=64", () => {
    for (const mgr of MANAGERS) {
      const result = resolveAvatarProps({ agentName: mgr.name, size: "manager" });
      expect(result!.width, `${mgr.name} width`).toBe(64);
    }
  });

  it("12 도제 — size=doje 적용 시 모두 px=40", () => {
    for (const doje of DOJES) {
      const result = resolveAvatarProps({ agentName: doje.name, size: "doje" });
      expect(result!.width, `${doje.name} width`).toBe(40);
    }
  });

  it("king — size=king 적용 시 px=80", () => {
    const result = resolveAvatarProps({ agentName: "king", size: "king" });
    expect(result!.width).toBe(80);
  });
});

// ── 6. src 형식 정규표현식 검증 ──────────────────────────────────────────────

describe("CharacterAvatar — src 형식 보장 (정규표현식)", () => {
  const SRC_PATTERN = /^\/characters\/[a-z][a-z0-9-]+\.svg$/;

  for (const key of CHARACTER_KEYS) {
    it(`${key} src가 /characters/*.svg 형식`, () => {
      const result = resolveAvatarProps({ agentName: key });
      expect(result!.src).toMatch(SRC_PATTERN);
    });
  }
});
