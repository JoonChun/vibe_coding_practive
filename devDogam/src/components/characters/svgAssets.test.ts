// ── SVG 자산 정적 검증 — Phase 2 F 도제 픽셀아트 배포 확인 ──────────────────
// 목적:
//   1. public/characters/ 에 17개 SVG 파일 전부 존재
//   2. 각 SVG XML 유효성 (루트 <svg> 태그 존재)
//   3. SVG 속성 정합: viewBox="0 0 32 32", shape-rendering="crispEdges"
//   4. king.svg 는 width/height=80, 나머지는 64
//   5. 12 도제 SVG가 실제 픽셀아트(> 2 KB) — placeholder(< 500B) 아님
//
// 환경: vitest (node), fs 모듈로 파일 직접 읽기 — jsdom 불필요

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync, statSync } from "fs";
import { join } from "path";

// ── 상수 ─────────────────────────────────────────────────────────────────────

const CHARACTERS_DIR = join(__dirname, "../../../public/characters");

/** 1왕 + 4매니저 + 12도제 = 17개 */
const ALL_CHARACTER_KEYS = [
  "king",
  "planner-dojeon",
  "implementer-yeongsil",
  "reviewer-sunsin",
  "ideator-yagyong",
  // planner-dojeon 소속 도제 3인
  "planning-hojo",
  "uiux-hwawon",
  "docs-sagwan",
  // implementer-yeongsil 소속 도제 4인
  "frontend-dancheong",
  "backend-gigwan",
  "infra-tomok",
  "integration-tongsin",
  // reviewer-sunsin 소속 도제 3인
  "security-chukhu",
  "perf-uiwon",
  "test-gungwan",
  // ideator-yagyong 소속 도제 2인
  "research-jeja",
  "visual-hwagong",
] as const;

/** 매니저급 및 일반 도제(왕 제외) — width/height 64 */
const STANDARD_64_KEYS = ALL_CHARACTER_KEYS.filter((k) => k !== "king");

/** 12 도제만 (placeholder 체크 대상) */
const DOJE_KEYS = [
  "planning-hojo",
  "uiux-hwawon",
  "docs-sagwan",
  "frontend-dancheong",
  "backend-gigwan",
  "infra-tomok",
  "integration-tongsin",
  "security-chukhu",
  "perf-uiwon",
  "test-gungwan",
  "research-jeja",
  "visual-hwagong",
] as const;

// ── 헬퍼 ─────────────────────────────────────────────────────────────────────

function svgPath(name: string): string {
  return join(CHARACTERS_DIR, `${name}.svg`);
}

function readSvg(name: string): string {
  return readFileSync(svgPath(name), "utf-8");
}

/** SVG 파일에서 루트 <svg ...> 태그 문자열 추출 (멀티라인 주석 건너뜀) */
function extractSvgTag(content: string): string | null {
  // HTML 주석 제거 후 첫 번째 <svg ...> 추출
  const stripped = content.replace(/<!--[\s\S]*?-->/g, "");
  const match = stripped.match(/<svg\s[^>]*>/);
  return match ? match[0] : null;
}

// ── 1. 파일 존재 검증 ─────────────────────────────────────────────────────────

describe("SVG 자산 — 파일 존재 (17개 전원)", () => {
  it("public/characters/ 디렉토리 존재", () => {
    expect(existsSync(CHARACTERS_DIR), "public/characters 디렉토리 없음").toBe(true);
  });

  for (const key of ALL_CHARACTER_KEYS) {
    it(`${key}.svg 파일 존재`, () => {
      expect(existsSync(svgPath(key)), `${key}.svg 없음`).toBe(true);
    });
  }
});

// ── 2. XML 유효성 (루트 <svg> 태그) ──────────────────────────────────────────

describe("SVG 자산 — XML 유효성 (루트 <svg> 태그)", () => {
  for (const key of ALL_CHARACTER_KEYS) {
    it(`${key}.svg 루트 <svg> 태그 포함`, () => {
      const content = readSvg(key);
      const tag = extractSvgTag(content);
      expect(tag, `${key}.svg에 <svg> 태그 없음`).not.toBeNull();
    });
  }

  for (const key of ALL_CHARACTER_KEYS) {
    it(`${key}.svg xmlns="http://www.w3.org/2000/svg" 선언`, () => {
      const content = readSvg(key);
      const tag = extractSvgTag(content);
      expect(tag, `${key}.svg xmlns 없음`).toContain(
        'xmlns="http://www.w3.org/2000/svg"'
      );
    });
  }
});

// ── 3. SVG 속성 정합 ──────────────────────────────────────────────────────────

describe("SVG 자산 — viewBox·shape-rendering 속성 정합 (전원)", () => {
  for (const key of ALL_CHARACTER_KEYS) {
    it(`${key}.svg viewBox="0 0 32 32"`, () => {
      const content = readSvg(key);
      const tag = extractSvgTag(content);
      expect(tag, `${key}.svg viewBox 불일치`).toContain('viewBox="0 0 32 32"');
    });
  }

  for (const key of ALL_CHARACTER_KEYS) {
    it(`${key}.svg shape-rendering="crispEdges"`, () => {
      const content = readSvg(key);
      const tag = extractSvgTag(content);
      expect(tag, `${key}.svg shape-rendering 없음`).toContain(
        'shape-rendering="crispEdges"'
      );
    });
  }
});

// ── 4. width/height 크기 정합 ────────────────────────────────────────────────

describe("SVG 자산 — width/height 크기 정합", () => {
  it("king.svg — width=80 height=80 (임금 특대)", () => {
    const content = readSvg("king");
    const tag = extractSvgTag(content);
    expect(tag).toContain('width="80"');
    expect(tag).toContain('height="80"');
  });

  for (const key of STANDARD_64_KEYS) {
    it(`${key}.svg — width=64 height=64 (표준 크기)`, () => {
      const content = readSvg(key);
      const tag = extractSvgTag(content);
      expect(tag, `${key}.svg width 불일치`).toContain('width="64"');
      expect(tag, `${key}.svg height 불일치`).toContain('height="64"');
    });
  }
});

// ── 5. 도제 SVG 파일 크기 (placeholder 탐지) ─────────────────────────────────

describe("SVG 자산 — 12 도제 픽셀아트 실질 크기 (placeholder > 2 KB)", () => {
  const PLACEHOLDER_MAX_BYTES = 500;
  const PIXEL_ART_MIN_BYTES = 2000;

  for (const key of DOJE_KEYS) {
    it(`${key}.svg > 2 KB (진짜 픽셀아트, placeholder 아님)`, () => {
      const size = statSync(svgPath(key)).size;
      expect(
        size,
        `${key}.svg 크기 ${size}B — placeholder(< ${PLACEHOLDER_MAX_BYTES}B) 의심`
      ).toBeGreaterThan(PIXEL_ART_MIN_BYTES);
    });
  }
});

// ── 6. 4 매니저·king 파일 크기 (기존 자산 무결성) ────────────────────────────

describe("SVG 자산 — 매니저 4인·king 파일 비어 있지 않음 (> 500 B)", () => {
  const MANAGERS_AND_KING = [
    "king",
    "planner-dojeon",
    "implementer-yeongsil",
    "reviewer-sunsin",
    "ideator-yagyong",
  ] as const;

  for (const key of MANAGERS_AND_KING) {
    it(`${key}.svg > 500 B`, () => {
      const size = statSync(svgPath(key)).size;
      expect(size, `${key}.svg 크기 ${size}B — 너무 작음`).toBeGreaterThan(500);
    });
  }
});
