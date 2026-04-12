import type { RawReview, Platform } from '@/types';
import { PLATFORM_SELECTORS } from '@/config/platformSelectors';
import {
  MAX_REVIEWS_PER_SESSION,
} from '@/constants';
import {
  randomDelay,
  extractText,
  extractRating,
  extractProductId,
  waitForNewElements,
} from './utils';

// waitForNewElements는 NaverCrawler에서만 사용

type ProgressCallback = (pagesScraped: number, totalReviews: number) => void;
type IsCancelledFn = () => boolean;

// ─── 쿠팡 선택자 상수 ─────────────────────────────────────────────────────

// 최신순 버튼: twc-text-bluegray-800 + twc-cursor-pointer + twc-inline-flex (사용자 확인)
const COUPANG_SORT_BTN = '[class*="twc-text-bluegray-800"][class*="twc-cursor-pointer"][class*="twc-inline-flex"]';

// 페이지네이션 컨테이너: data-page 속성으로 식별 (스타일 변경에도 안전)
const COUPANG_PAGINATION = '[data-page]';

// ─── 쿠팡 크롤러 (페이지네이션 + iframe 지원) ────────────────────────────

export class CoupangCrawler {
  private platform: Platform = 'coupang';
  private selectors = PLATFORM_SELECTORS['coupang'];
  private reviews: RawReview[] = [];
  private currentPage = 1;
  private productId: string;
  private onProgress: ProgressCallback;
  private maxReviews: number;
  private isCancelled: IsCancelledFn;
  /** 리뷰가 실제로 있는 document (메인 or iframe) */
  private searchDoc: Document = document;
  private seenIds = new Set<string>();

  constructor(
    onProgress: ProgressCallback,
    maxReviews: number = MAX_REVIEWS_PER_SESSION,
    isCancelled: IsCancelledFn = () => false,
  ) {
    this.productId = extractProductId(this.platform, window.location.href);
    this.onProgress = onProgress;
    this.maxReviews = maxReviews;
    this.isCancelled = isCancelled;
  }

  async run(): Promise<RawReview[]> {
    // 1단계: 상품평 탭 클릭 (메인 document에서 탐색)
    await this.clickReviewTab();
    await randomDelay(2000, 3000);

    // 2단계: 최신순 클릭 (메인 document에서 탐색)
    await this.clickLatestSort();
    await randomDelay(2000, 3000);

    // 3단계: 리뷰가 있는 document 확정 (메인 → iframe 순)
    await this.resolveSearchDocument();
    console.log(`[ReviewPick] searchDoc=${this.searchDoc === document ? 'main' : 'iframe'}, 리뷰 요소=${this.searchDoc.querySelectorAll(this.selectors.reviewContainer).length}개`);

    // 4단계: 항상 1페이지부터 수집 (사용자가 다른 페이지에 있을 수 있음)
    await this.goToFirstPage();

    // 5단계: 페이지 순회하며 리뷰 수집
    while (this.reviews.length < this.maxReviews) {
      if (this.isCancelled()) break;

      const pageAttr = this.searchDoc
        .querySelector(COUPANG_PAGINATION)
        ?.getAttribute('data-page');
      if (pageAttr) this.currentPage = parseInt(pageAttr, 10);

      this.collectPage();
      this.onProgress(this.currentPage, this.reviews.length);

      const hasNext = await this.clickNextPage();
      if (!hasNext) break;

      await randomDelay();
    }

    return this.reviews;
  }

  // 리뷰가 있는 document를 탐색: 메인 → 동일 origin iframe 순서
  private async resolveSearchDocument(): Promise<void> {
    // 메인 document에 있으면 그대로 사용
    if (document.querySelector(this.selectors.reviewContainer)) {
      this.searchDoc = document;
      return;
    }

    // iframe 내부 탐색 (동일 origin만 접근 가능)
    const iframes = Array.from(document.querySelectorAll<HTMLIFrameElement>('iframe'));
    for (const iframe of iframes) {
      try {
        const doc = iframe.contentDocument;
        if (!doc) continue;
        if (doc.querySelector(this.selectors.reviewContainer)) {
          this.searchDoc = doc;
          console.log('[ReviewPick] iframe에서 리뷰 발견:', iframe.src || '(no src)');
          return;
        }
      } catch {
        // cross-origin iframe — 접근 불가, 스킵
      }
    }

    console.warn('[ReviewPick] 리뷰 요소를 찾지 못했습니다 (메인+iframe 모두 탐색).');
    this.searchDoc = document;
  }

  // 항상 1페이지부터 시작 — 현재 페이지가 1이 아니면 "1" 버튼 클릭
  private async goToFirstPage(): Promise<void> {
    const pagination = this.searchDoc.querySelector<HTMLElement>(COUPANG_PAGINATION);
    if (!pagination) return;

    const currentPage = parseInt(pagination.getAttribute('data-page') ?? '1', 10);
    if (currentPage === 1) return;

    console.log(`[ReviewPick] 현재 ${currentPage}페이지 → 1페이지로 이동`);

    const btns = Array.from(pagination.querySelectorAll<HTMLElement>('button'));
    const firstPageBtn = btns.find((btn) => btn.textContent?.trim() === '1');
    if (!firstPageBtn) return;

    const previousCount = this.searchDoc.querySelectorAll(this.selectors.reviewContainer).length;
    firstPageBtn.click();
    await this.waitForPageChange(previousCount, 4000);
    await randomDelay(500, 1000);
  }

  // "상품평" 탭 클릭 (메인 document 기준)
  private async clickReviewTab(): Promise<void> {
    const candidates = Array.from(
      document.querySelectorAll<HTMLElement>('a, button, li[role="tab"]'),
    );
    const tab = candidates.find(
      (el) => el.textContent?.trim().replace(/\s+/g, '') === '상품평',
    );
    if (tab) {
      console.log('[ReviewPick] 상품평 탭 클릭');
      tab.click();
    } else {
      console.warn('[ReviewPick] 상품평 탭을 찾지 못했습니다 — 현재 페이지에서 진행합니다.');
    }
  }

  // "최신순" 버튼 클릭 (메인 document 기준)
  private async clickLatestSort(): Promise<void> {
    const candidates = Array.from(
      document.querySelectorAll<HTMLElement>(COUPANG_SORT_BTN),
    );
    const btn = candidates.find((el) => el.textContent?.trim() === '최신순');
    if (btn) {
      console.log('[ReviewPick] 최신순 클릭');
      btn.click();
    } else {
      console.warn('[ReviewPick] 최신순 버튼을 찾지 못했습니다.');
    }
  }

  // 현재 페이지의 텍스트 리뷰 수집 (searchDoc 기준)
  private collectPage(): void {
    const containers = this.searchDoc.querySelectorAll(this.selectors.reviewContainer);
    console.log(`[ReviewPick] 페이지 ${this.currentPage} — ${containers.length}개`);

    containers.forEach((container, i) => {
      const text = this.selectors.reviewText
        ? extractText(container, this.selectors.reviewText)
        : container.textContent?.trim() ?? '';

      if (!text) return;

      const id = `${this.platform}-p${this.currentPage}-${i}`;
      if (this.seenIds.has(id)) return;
      this.seenIds.add(id);
      this.reviews.push({
        id,
        platform: this.platform,
        text,
        rating: extractRating(container, this.selectors.rating),
        author: extractText(container, this.selectors.author),
        date: extractText(container, this.selectors.date),
        productId: this.productId,
      });
    });
  }

  // 다음 페이지 버튼 클릭 후 새 리뷰 로드 대기 (searchDoc 기준)
  private async clickNextPage(): Promise<boolean> {
    const nextBtn = this.findNextPageButton();
    if (!nextBtn) return false;

    const previousCount = this.searchDoc.querySelectorAll(
      this.selectors.reviewContainer,
    ).length;

    nextBtn.click();

    // 새 리뷰가 로드될 때까지 대기 (최대 4초)
    await this.waitForPageChange(previousCount, 4000);
    return true;
  }

  // 페이지 전환 후 리뷰 수가 바뀌거나 timeout이 될 때까지 대기
  private waitForPageChange(previousCount: number, timeout = 4000): Promise<void> {
    return new Promise((resolve) => {
      const timer = setTimeout(resolve, timeout);
      const observer = new MutationObserver(() => {
        const current = this.searchDoc.querySelectorAll(
          this.selectors.reviewContainer,
        ).length;
        if (current !== previousCount) {
          clearTimeout(timer);
          observer.disconnect();
          resolve();
        }
      });
      observer.observe(this.searchDoc.body, { childList: true, subtree: true });
    });
  }

  // 페이지네이션 컨테이너의 마지막 버튼 = 다음(→) 화살표 (searchDoc 기준)
  private findNextPageButton(): HTMLElement | null {
    const pagination = this.searchDoc.querySelector<HTMLElement>(COUPANG_PAGINATION);
    if (!pagination) return null;

    const btns = Array.from(pagination.querySelectorAll<HTMLElement>('button'));
    const lastBtn = btns[btns.length - 1];

    if (!lastBtn || this.isDisabled(lastBtn)) return null;
    return lastBtn;
  }

  private isDisabled(el: HTMLElement): boolean {
    return (
      el.getAttribute('disabled') !== null ||
      el.getAttribute('aria-disabled') === 'true' ||
      el.classList.contains('disabled')
    );
  }
}

// ─── 네이버 선택자 상수 ──────────────────────────────────────────────────

// 리뷰 탭: data-name="REVIEW" (스타일 변경에도 안전한 data 속성)
const NAVER_REVIEW_TAB = 'a[data-name="REVIEW"]';

// 최신순 버튼: data-shp-contents-id 기반 (클래스명은 obfuscated되어 불안정)
const NAVER_SORT_LATEST = 'a[data-shp-contents-id="최신순"]';

// 페이지 이동 버튼(이전/다음): role="button" + data-shp-contents-type="pgn"
// 이전: aria-hidden="true" (1페이지일 때), 다음: aria-hidden="false"
const NAVER_PAGE_CONTROLS = 'a[data-shp-contents-type="pgn"][role="button"]';

// ─── 네이버 크롤러 (페이지네이션) ────────────────────────────────────────

export class NaverCrawler {
  private platform: Platform = 'naver';
  private selectors = PLATFORM_SELECTORS['naver'];
  private reviews: RawReview[] = [];
  private currentPage = 1;
  private productId: string;
  private onProgress: ProgressCallback;
  private maxReviews: number;
  private isCancelled: IsCancelledFn;
  private seenIds = new Set<string>();

  constructor(
    onProgress: ProgressCallback,
    maxReviews: number = MAX_REVIEWS_PER_SESSION,
    isCancelled: IsCancelledFn = () => false,
  ) {
    this.productId = extractProductId(this.platform, window.location.href);
    this.onProgress = onProgress;
    this.maxReviews = maxReviews;
    this.isCancelled = isCancelled;
  }

  async run(): Promise<RawReview[]> {
    // 1단계: 리뷰 탭 클릭
    await this.clickReviewTab();
    await randomDelay(2000, 3000);

    // 2단계: 최신순 클릭
    await this.clickLatestSort();
    await randomDelay(1500, 2500);

    // 3단계: 페이지 순회하며 리뷰 수집
    while (this.reviews.length < this.maxReviews) {
      if (this.isCancelled()) break;

      this.collectPage();
      this.onProgress(this.currentPage, this.reviews.length);

      const hasNext = await this.clickNextPage();
      if (!hasNext) break;

      await randomDelay();
      this.currentPage++;
    }

    return this.reviews;
  }

  // "리뷰" 탭 클릭 — data-name="REVIEW"
  private async clickReviewTab(): Promise<void> {
    const tab = document.querySelector<HTMLElement>(NAVER_REVIEW_TAB);
    if (tab) {
      console.log('[ReviewPick] 네이버 리뷰 탭 클릭');
      tab.click();
    } else {
      console.warn('[ReviewPick] 네이버 리뷰 탭을 찾지 못했습니다 — 현재 페이지에서 진행합니다.');
    }
  }

  // "최신순" 버튼 클릭 — data-shp-contents-id="최신순"
  private async clickLatestSort(): Promise<void> {
    const btn = document.querySelector<HTMLElement>(NAVER_SORT_LATEST);
    if (btn) {
      console.log('[ReviewPick] 네이버 최신순 클릭');
      btn.click();
    } else {
      console.warn('[ReviewPick] 네이버 최신순 버튼을 찾지 못했습니다.');
    }
  }

  private collectPage(): void {
    if (!this.selectors.reviewContainer) return;

    // 구매자 프로필 섹션(.RVbIFwX5dY) 내부 span은 리뷰 텍스트가 아니므로 제외
    const allContainers = Array.from(
      document.querySelectorAll<Element>(this.selectors.reviewContainer),
    );
    const containers = allContainers.filter((el) => !el.closest('.RVbIFwX5dY'));
    console.log(
      `[ReviewPick] 네이버 페이지 ${this.currentPage} — ${containers.length}개 (전체 ${allContainers.length}개 중 프로필 제외)`,
    );

    containers.forEach((container, i) => {
      const text = this.selectors.reviewText
        ? extractText(container, this.selectors.reviewText)
        : container.textContent?.trim() ?? '';
      if (!text) return;

      // 구매자 프로필과 속성 평가를 조상 탐색으로 추출
      const metadata = this.extractBuyerMetadata(container);
      const fullText = metadata ? `${text}\n${metadata}` : text;

      const id = `${this.platform}-p${this.currentPage}-${i}`;
      if (this.seenIds.has(id)) return;
      this.seenIds.add(id);
      this.reviews.push({
        id,
        platform: this.platform,
        text: fullText,
        rating: extractRating(container, this.selectors.rating),
        author: extractText(container, this.selectors.author),
        date: extractText(container, this.selectors.date),
        productId: this.productId,
      });
    });
  }

  /**
   * 리뷰 요소의 조상 DOM에서 구매자 프로필(.RVbIFwX5dY)과
   * 속성 평가(.h8uqAeqIe7)를 추출해 문자열로 반환
   *
   * 구조 예시:
   *   .RVbIFwX5dY > ul > li
   *     span.YtlfLnnteK "거주인원"
   *     span.MX91DFZo2F > span "5인"
   *     span.MX91DFZo2F > span "취학자녀 가정"
   *     span.YtlfLnnteK "식이관심사"
   *     span.MX91DFZo2F > span "친환경"
   *   .h8uqAeqIe7
   *     div.YtlfLnnteK "신선함"
   *     div.MX91DFZo2F "신선해요"
   */
  private extractBuyerMetadata(el: Element): string {
    let ancestor: Element | null = el.parentElement;
    for (let depth = 0; depth < 8; depth++) {
      if (!ancestor) break;

      const profileEl = ancestor.querySelector('.RVbIFwX5dY');
      const ratingsEl = ancestor.querySelector('.h8uqAeqIe7');

      if (!profileEl && !ratingsEl) {
        ancestor = ancestor.parentElement;
        continue;
      }

      const parts: string[] = [];

      // 구매자 프로필: li 내 label-value 쌍 추출
      if (profileEl) {
        const listItems = profileEl.querySelectorAll<HTMLElement>('li');
        listItems.forEach((li) => {
          const children = Array.from(li.children);
          let currentLabel = '';
          const currentValues: string[] = [];

          children.forEach((child) => {
            if (child.classList.contains('YtlfLnnteK')) {
              if (currentLabel && currentValues.length) {
                parts.push(`${currentLabel}: ${currentValues.join(', ')}`);
              }
              currentLabel = child.textContent?.trim() ?? '';
              currentValues.length = 0;
            } else if (child.classList.contains('MX91DFZo2F')) {
              const v = child.textContent?.trim();
              if (v) currentValues.push(v);
            }
          });

          if (currentLabel && currentValues.length) {
            parts.push(`${currentLabel}: ${currentValues.join(', ')}`);
          }
        });
      }

      // 속성 평가: label-value 순서쌍 추출
      if (ratingsEl) {
        const children = Array.from(ratingsEl.children);
        let j = 0;
        while (j < children.length - 1) {
          if (
            children[j].classList.contains('YtlfLnnteK') &&
            children[j + 1].classList.contains('MX91DFZo2F')
          ) {
            const label = children[j].textContent?.trim();
            const value = children[j + 1].textContent?.trim();
            if (label && value) parts.push(`${label}: ${value}`);
            j += 2;
          } else {
            j++;
          }
        }
      }

      return parts.length ? `[구매자 정보: ${parts.join(' | ')}]` : '';
    }

    return '';
  }

  private async clickNextPage(): Promise<boolean> {
    // 이전/다음 버튼 중 텍스트가 "다음"인 버튼을 탐색
    const ctrlBtns = Array.from(document.querySelectorAll<HTMLElement>(NAVER_PAGE_CONTROLS));
    const nextBtn = ctrlBtns.find((btn) => btn.textContent?.trim() === '다음');

    if (!nextBtn) return false;

    // aria-hidden="true" 이면 마지막 페이지 (다음 버튼 비활성)
    if (nextBtn.getAttribute('aria-hidden') === 'true') return false;

    const previousCount = document.querySelectorAll(this.selectors.reviewContainer).length;
    nextBtn.click();

    try {
      await waitForNewElements(this.selectors.reviewContainer, previousCount, 4000);
      return true;
    } catch {
      return false;
    }
  }
}
