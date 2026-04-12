import type { ExtensionMessage } from '@/types';
import { detectPlatform } from './utils';
import { CoupangCrawler, NaverCrawler } from './crawler';

// 이중 주입 방지: 같은 익스텐션의 콘텐츠 스크립트는 isolated world를 공유하므로
// window 객체 플래그로 두 번째 주입 시 중복 리스너 등록을 막는다.
const _w = window as Window & { __reviewPickLoaded?: boolean };
if (_w.__reviewPickLoaded) {
  // 이미 초기화됨 → 아무것도 하지 않음
} else {
_w.__reviewPickLoaded = true;

// 중복 실행 방지
let isCrawling = false;

/**
 * 진행 상황을 팝업으로 전달
 */
function sendProgress(pagesScraped: number, totalReviews: number) {
  const msg: ExtensionMessage = {
    action: 'CRAWL_PROGRESS',
    pagesScraped,
    totalReviews,
  };
  chrome.runtime.sendMessage(msg).catch(() => {
    // 팝업이 닫혀 있을 경우 무시
  });
}

/**
 * 상품명 추출 (페이지 타이틀 또는 h1 태그 기반)
 */
function extractProductName(): string {
  const h1 = document.querySelector('h1');
  if (h1?.textContent?.trim()) return h1.textContent.trim();
  return document.title.split('|')[0].trim();
}

// ─── 메시지 리스너 ────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener(
  (message: ExtensionMessage, _sender, sendResponse) => {
    if (message.action !== 'START_CRAWL') return false;
    if (isCrawling) {
      sendResponse({ ok: false, error: '이미 크롤링 중입니다.' });
      return false;
    }

    const platform = detectPlatform();
    if (!platform) {
      sendResponse({ ok: false, error: '지원하지 않는 플랫폼입니다.' });
      return false;
    }

    isCrawling = true;
    sendResponse({ ok: true });

    (async () => {
      try {
        let reviews;
        const maxReviews = message.maxReviews;

        if (platform === 'coupang') {
          const crawler = new CoupangCrawler(sendProgress, maxReviews);
          reviews = await crawler.run();
        } else {
          const crawler = new NaverCrawler(sendProgress, maxReviews);
          reviews = await crawler.run();
        }

        if (reviews.length === 0) {
          throw new Error('수집된 리뷰가 없습니다. 상품평 탭을 직접 열어둔 상태에서 다시 시도해주세요.');
        }

        const productName = extractProductName();
        const productUrl = window.location.href;

        const completeMsg: ExtensionMessage = {
          action: 'CRAWL_COMPLETE',
          reviews,
          productName,
          productUrl,
        };
        chrome.runtime.sendMessage(completeMsg);
      } catch (err) {
        console.error('[ReviewPick] 크롤링 오류:', err);
        // 크롤링 오류를 background로 전달하여 사용자에게 알림
        const errMsg = err instanceof Error ? err.message : '크롤링 중 알 수 없는 오류가 발생했습니다.';
        chrome.runtime.sendMessage({ action: 'ANALYSIS_ERROR', message: errMsg } as ExtensionMessage).catch(() => {});
      } finally {
        isCrawling = false;
      }
    })();

    return false;
  },
);

} // end: __reviewPickLoaded guard
