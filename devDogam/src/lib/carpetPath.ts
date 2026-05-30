/**
 * carpetPath.ts — 매니저 카펫 이동 & 절 choreography 상수 모음
 *
 * 시방서 §7 keyframe 순서:
 *   1. 자기 자리 → 카펫 입구 (두 발짝, x 이동)        STEP_TO_CARPET_MS
 *   2. 카펫 따라 ↑ 계단 앞까지 (y 이동)               CARPET_TO_STAIRS_MS
 *   3. 계단 앞 절 최심 (scaleY 0.92, rotate 5°)       BOW_DOWN_MS
 *   4. 절 복귀 (scaleY 1, rotate 0)                   BOW_UP_MS
 *   5. 카펫 따라 ↓ 자기 자리 복귀                      RETURN_MS
 *
 * 합계: 300 + 500 + 400 + 200 + 700 = 2100ms = BOW_DURATION_MS
 */

/** 매니저가 자기 자리에서 카펫 입구까지 두 발짝 — x 이동량 (px, 절댓값) §7-step1 */
export const CARPET_STEP_X_PX = 80;

/** 카펫 중앙 (계단 앞) x 이동량 (px, 절댓값) §7-step2 */
export const CARPET_CENTER_X_PX = 160;

/** 카펫 따라 ↑ 이동량 (px, 음수 = 위 방향) §7-step2
 * v3: 매니저 top=58~76%에서 계단(SVG y≈342) 도달 위해 -60px로 확장.
 * 정도전·이순신은 +20px 여유로 약간 위까지 갔다 복귀, 정약용·장영실은 카펫 중간 → 계단 앞 도달
 */
export const CARPET_Y_PX = -60;

/**
 * 도제가 카펫 끝에서 시작하는 y 위치 (viewport-relative).
 * §6 — 화면 하단의 카펫 끝 영역에서 페이드인/슬라이드.
 */
export const DOJE_CARPET_START_Y = "30vh";

/** 매니저 절 모션 총 길이 (ms). 자기 자리 → 카펫 → 계단 → 절 → 복귀. §7 */
export const BOW_DURATION_MS = 2100;

// ── 각 keyframe 단계별 duration (ms) ──────────────────────────────────────

/** §7-step1: 자기 자리 → 카펫 입구 (두 발짝, x만 이동) */
export const STEP_TO_CARPET_MS = 300;

/** §7-step2: 카펫 입구 → 계단 앞 (카펫 따라 ↑, y 이동) */
export const CARPET_TO_STAIRS_MS = 500;

/** §7-step3: 절 최심 (scaleY 0.92, rotate 5°) */
export const BOW_DOWN_MS = 400;

/** §7-step4: 절 복귀 (scaleY 1, rotate 0) */
export const BOW_UP_MS = 200;

/** §7-step5: 카펫 따라 ↓ 자기 자리 복귀 */
export const RETURN_MS = 700;
