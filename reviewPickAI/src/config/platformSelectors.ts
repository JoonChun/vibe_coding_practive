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
    reviewContainer: '',   // TODO: 네이버 개별 리뷰 컨테이너 선택자
    reviewText: '',        // TODO: 네이버 리뷰 본문 선택자
    rating: '',            // TODO: 네이버 별점 선택자
    author: '',            // TODO: 네이버 작성자 선택자
    date: '',              // TODO: 네이버 날짜 선택자
    nextPageButton: '',    // TODO: 네이버 다음 페이지 버튼 선택자
    scrollTarget: '',      // TODO: 네이버 스크롤 대상 선택자
  },
};
