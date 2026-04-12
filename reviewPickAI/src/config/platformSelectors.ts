import type { PlatformSelectorConfig } from '@/types';

/**
 * 플랫폼별 CSS 선택자 설정
 *
 * ⚠️  사용자가 직접 채워야 합니다.
 *     각 플랫폼의 실제 DOM 구조를 확인하고 아래 빈 문자열을 교체하세요.
 *
 * 예시:
 *   reviewContainer: '.sdp-review__article__list__review'
 *   reviewText: '.sdp-review__article__list__review__content'
 */
export const PLATFORM_SELECTORS: Record<string, PlatformSelectorConfig> = {
  coupang: {
    // 리뷰 텍스트 span: translate="no" + twc-bg-white (사용자 확인된 구조)
    // <span class="twc-bg-white" translate="no">리뷰내용</span>
    reviewContainer: 'span[translate="no"][class*="twc-bg"]',
    reviewText: '', // container 자체가 텍스트 → textContent 직접 사용
    rating: '',            // 텍스트 수집 우선
    author: '',
    date: '',
    nextPageButton: '',    // crawler.ts 내부에서 COUPANG_PAGINATION_SELECTOR 기반으로 탐색
    scrollTarget: '',      // 페이지네이션 방식 (스크롤 불필요)
  },
  naver: {
    // 리뷰 본문 span — 텍스트를 직접 textContent로 사용
    reviewContainer: 'span.MX91DFZo2F',
    reviewText: '',        // container 자체가 텍스트 → textContent 직접 사용
    rating: '',
    author: '',
    date: '',
    nextPageButton: '',    // crawler.ts 내부 NAVER_* 상수로 처리
    scrollTarget: '',      // 페이지네이션 방식 (스크롤 불필요)
  },
};
