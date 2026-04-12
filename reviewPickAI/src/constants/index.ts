// ─── 크롤링 설정 ─────────────────────────────────────────────────────────

/** 한 번에 Gemini에 보낼 리뷰 수 */
export const CHUNK_SIZE = 100;

/** 봇 탐지 방어: 최소 딜레이 (ms) */
export const MIN_DELAY_MS = 800;

/** 봇 탐지 방어: 최대 딜레이 (ms) */
export const MAX_DELAY_MS = 2500;

/** 무한 스크롤 최대 시도 횟수 */
export const MAX_SCROLL_ATTEMPTS = 30;

/** 스크롤 후 새 리뷰 대기 시간 (ms) */
export const SCROLL_WAIT_MS = 1500;

/** 페이지당 최대 수집 리뷰 수 (메모리 보호) */
export const MAX_REVIEWS_PER_SESSION = 1000;

// ─── Gemini 설정 ─────────────────────────────────────────────────────────

export const GEMINI_MODEL = 'gemini-3-flash-preview';

export const GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta/models';

// ─── chrome.storage 키 ────────────────────────────────────────────────────

export const STORAGE_KEYS = {
  CURRENT_ANALYSIS: 'currentAnalysis',
  COMPARISON_SESSIONS: 'comparisonSessions',
  GEMINI_API_KEY: 'geminiApiKey',
  USER_PREFERENCES: 'userPreferences',
  CRAWL_STATE: 'crawlState',
  MAX_REVIEWS: 'maxReviews',
} as const;

// ─── 디자인 토큰 ─────────────────────────────────────────────────────────

export const COLORS = {
  PRIMARY: '#0051FF',
  NEGATIVE: '#F04452',
  POSITIVE: '#0EA5E9',
  NEUTRAL: '#6B7684',
  BG: '#F2F4F6',
  SURFACE: '#FFFFFF',
} as const;
