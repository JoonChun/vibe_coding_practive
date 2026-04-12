import type { Platform } from '@/types';
import { MIN_DELAY_MS, MAX_DELAY_MS } from '@/constants';

/**
 * 봇 탐지 방어용 랜덤 딜레이
 */
export function randomDelay(
  min: number = MIN_DELAY_MS,
  max: number = MAX_DELAY_MS,
): Promise<void> {
  const ms = Math.floor(Math.random() * (max - min + 1)) + min;
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * 안전한 텍스트 추출 (선택자가 없거나 요소가 없으면 빈 문자열 반환)
 */
export function extractText(container: Element, selector: string): string {
  if (!selector) return '';
  const el = container.querySelector(selector);
  return el?.textContent?.trim() ?? '';
}

/**
 * 별점 추출 — 텍스트에서 숫자 파싱 (예: "4.5점", "★★★★☆" → 4)
 */
export function extractRating(container: Element, selector: string): number {
  if (!selector) return 0;
  const el = container.querySelector(selector);
  if (!el) return 0;

  const text = el.textContent?.trim() ?? '';
  // "4.5" 또는 "4" 형식
  const match = text.match(/(\d+(\.\d+)?)/);
  if (match) return Math.min(5, parseFloat(match[1]));

  // aria-label 등에서 파싱 시도
  const aria = el.getAttribute('aria-label') ?? '';
  const ariaMatch = aria.match(/(\d+(\.\d+)?)/);
  if (ariaMatch) return Math.min(5, parseFloat(ariaMatch[1]));

  return 0;
}

/**
 * 현재 페이지의 플랫폼 감지
 */
export function detectPlatform(hostname?: string): Platform | null {
  const host = hostname ?? window.location.hostname;
  if (host.includes('coupang.com')) return 'coupang';
  if (host.includes('naver.com')) return 'naver';
  return null;
}

/**
 * URL에서 상품 ID 추출
 */
export function extractProductId(platform: Platform, url: string): string {
  try {
    const parsed = new URL(url);
    if (platform === 'coupang') {
      // 예: /vp/products/12345678
      const match = parsed.pathname.match(/\/products\/(\d+)/);
      return match?.[1] ?? parsed.pathname;
    }
    if (platform === 'naver') {
      // 예: /catalog/12345678 또는 query params
      const catalogMatch = parsed.pathname.match(/\/catalog\/(\d+)/);
      if (catalogMatch) return catalogMatch[1];
      return parsed.searchParams.get('nvMid') ?? parsed.pathname;
    }
  } catch {
    // URL 파싱 실패
  }
  return url;
}

/**
 * MutationObserver를 활용한 새 요소 대기
 */
export function waitForNewElements(
  selector: string,
  previousCount: number,
  timeout = 3000,
): Promise<NodeList> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      observer.disconnect();
      reject(new Error('timeout'));
    }, timeout);

    const observer = new MutationObserver(() => {
      const nodes = document.querySelectorAll(selector);
      if (nodes.length > previousCount) {
        clearTimeout(timer);
        observer.disconnect();
        resolve(nodes);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
  });
}
