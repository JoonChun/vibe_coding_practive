import type {
  ExtensionMessage,
  RawReview,
  TaggedReview,
  AnalysisResult,
  MindmapNode,
  GeminiAnalysisChunk,
  SentimentLabel,
} from '@/types';
import { CHUNK_SIZE, STORAGE_KEYS } from '@/constants';
import type { CrawlState } from '@/types';
import { analyzeReviews, mergeChunks } from '@/gemini/client';
import { storage } from '@/utils/storage';
import { v4 as uuidv4 } from 'uuid';

// ─── 배지 초기 색상 설정 ─────────────────────────────────────────────────

chrome.action.setBadgeBackgroundColor({ color: '#0051FF' });

// ─── 메시지 라우터 ────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener(
  (message: ExtensionMessage, _sender, sendResponse) => {
    switch (message.action) {
      case 'CRAWL_PROGRESS':
        saveCrawlState({
          phase: 'crawling',
          pages: message.pagesScraped,
          reviews: message.totalReviews,
          chunksComplete: 0,
          totalChunks: 0,
          updatedAt: Date.now(),
        });
        chrome.action.setBadgeText({ text: String(message.totalReviews) });
        break;

      case 'ANALYSIS_PROGRESS':
        saveCrawlState({
          phase: 'analyzing',
          pages: 0,
          reviews: 0,
          chunksComplete: message.chunksComplete,
          totalChunks: message.totalChunks,
          updatedAt: Date.now(),
        });
        chrome.action.setBadgeText({
          text: `${message.chunksComplete}/${message.totalChunks}`,
        });
        break;

      case 'CRAWL_CANCELLED':
        saveCrawlState({
          phase: 'done',
          pages: 0,
          reviews: 0,
          chunksComplete: 0,
          totalChunks: 0,
          updatedAt: Date.now(),
        });
        chrome.action.setBadgeText({ text: '' });
        sendResponse({ ok: true });
        break;

      case 'CRAWL_COMPLETE':
        handleCrawlComplete(message.reviews, message.productName, message.productUrl);
        sendResponse({ ok: true });
        break;

      case 'RE_ANALYZE':
        handleReAnalyze(message.keyword);
        sendResponse({ ok: true });
        break;

      case 'COMPARE_ADD':
        handleCompareAdd(message.url);
        sendResponse({ ok: true });
        break;
    }
    return false;
  },
);

// ─── 크롤링 완료 처리 ────────────────────────────────────────────────────

async function handleCrawlComplete(
  reviews: RawReview[],
  productName: string,
  productUrl: string,
) {
  try {
    if (reviews.length === 0) {
      throw new Error('수집된 리뷰가 없습니다. 상품평 탭을 직접 열어둔 상태에서 다시 시도해주세요.');
    }

    const apiKey = await storage.get(STORAGE_KEYS.GEMINI_API_KEY as keyof import('@/types').StorageSchema) as string | null;
    if (!apiKey) {
      throw new Error('Gemini API 키가 설정되지 않았습니다.');
    }

    // 청크 분할 및 순차 처리 (rate limit 준수)
    const chunks = chunkArray(reviews, CHUNK_SIZE);
    const partialResults: GeminiAnalysisChunk[] = [];

    for (let i = 0; i < chunks.length; i++) {
      const offset = i * CHUNK_SIZE;

      // 청크 시작 전 진행 상황 브로드캐스트
      broadcastProgress(i, chunks.length);

      const chunkResult = await analyzeReviews(chunks[i], apiKey, offset);
      partialResults.push(chunkResult);

      // 청크 완료 후 진행 상황 업데이트
      broadcastProgress(i + 1, chunks.length);
    }

    // 청크 병합
    const merged = mergeChunks(partialResults);

    // AnalysisResult 구성
    const result = buildAnalysisResult(
      merged,
      reviews,
      productName,
      productUrl,
    );

    // chrome.storage에 저장
    await storage.set(
      STORAGE_KEYS.CURRENT_ANALYSIS as keyof import('@/types').StorageSchema,
      result as never,
    );

    // 대시보드 탭 열기
    chrome.tabs.create({
      url: chrome.runtime.getURL('pages/dashboard.html'),
    });

    broadcastAnalysisComplete(result);

    // 완료 상태 저장 + 배지 클리어 + 알림
    saveCrawlState({
      phase: 'done',
      pages: 0,
      reviews: result.totalReviews,
      chunksComplete: 0,
      totalChunks: 0,
      updatedAt: Date.now(),
    });
    chrome.action.setBadgeText({ text: '' });
    chrome.notifications.create({
      type: 'basic',
      iconUrl: chrome.runtime.getURL('icons/icon48.png'),
      title: 'ReviewPick AI — 분석 완료!',
      message: `${result.productName} 리뷰 ${result.totalReviews}개 분석이 완료됐습니다.`,
    });
  } catch (err) {
    console.error('[ReviewPick] 분석 오류:', err);
    saveCrawlState({
      phase: 'error',
      pages: 0,
      reviews: 0,
      chunksComplete: 0,
      totalChunks: 0,
      errorMsg: err instanceof Error ? err.message : '알 수 없는 오류',
      updatedAt: Date.now(),
    });
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#F04452' });

    const errMsg = err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.';
    chrome.runtime.sendMessage({ action: 'ANALYSIS_ERROR', message: errMsg } as ExtensionMessage).catch(() => {});
    chrome.notifications.create({
      type: 'basic',
      iconUrl: chrome.runtime.getURL('icons/icon48.png'),
      title: 'ReviewPick AI — 오류 발생',
      message: errMsg,
    });
  }
}

// ─── 키워드 필터 재분석 ───────────────────────────────────────────────────

async function handleReAnalyze(keyword: string) {
  try {
    const currentAnalysis = await storage.get(
      STORAGE_KEYS.CURRENT_ANALYSIS as keyof import('@/types').StorageSchema,
    ) as AnalysisResult | null;

    if (!currentAnalysis) return;

    const apiKey = await storage.get(
      STORAGE_KEYS.GEMINI_API_KEY as keyof import('@/types').StorageSchema,
    ) as string | null;

    if (!apiKey) return;

    // 키워드 포함 리뷰만 필터 (원본 reviews 전체에서 필터링)
    const filtered = currentAnalysis.reviews.filter((r) =>
      r.text.toLowerCase().includes(keyword.toLowerCase()),
    );

    if (filtered.length === 0) {
      console.warn(`[ReviewPick] 재분석: "${keyword}" 포함 리뷰 없음`);
      return;
    }

    const chunks = chunkArray(filtered, CHUNK_SIZE);
    const partialResults: GeminiAnalysisChunk[] = [];

    for (let i = 0; i < chunks.length; i++) {
      // 재분석 청크 시작 전 진행 상황 브로드캐스트
      broadcastProgress(i, chunks.length);
      saveCrawlState({
        phase: 'analyzing',
        pages: 0,
        reviews: filtered.length,
        chunksComplete: i,
        totalChunks: chunks.length,
        updatedAt: Date.now(),
      });
      chrome.action.setBadgeText({ text: `${i}/${chunks.length}` });

      const chunkResult = await analyzeReviews(chunks[i], apiKey, i * CHUNK_SIZE);
      partialResults.push(chunkResult);

      // 청크 완료 후 진행 상황 업데이트
      broadcastProgress(i + 1, chunks.length);
      chrome.action.setBadgeText({ text: `${i + 1}/${chunks.length}` });
    }

    const merged = mergeChunks(partialResults);
    const filteredResult = buildAnalysisResult(
      merged,
      filtered,
      currentAnalysis.productName,
      currentAnalysis.productUrl,
    );

    // 원본 데이터 유실 방지: currentAnalysis의 원본 reviews를 보존하고
    // 재분석 결과는 별도 필드로 병합하여 저장
    const mergedResult: AnalysisResult = {
      ...currentAnalysis,          // 원본 id, reviews(전체), productName, platform 등 유지
      // 재분석 결과로 갱신되는 항목만 덮어쓰기
      sentiment: filteredResult.sentiment,
      summary: filteredResult.summary,
      keywords: filteredResult.keywords,
      mindmapRoot: filteredResult.mindmapRoot,
      // reviews는 원본 전체 유지 (태그만 필터된 결과로 업데이트)
      reviews: currentAnalysis.reviews.map((r) => {
        const updated = filteredResult.reviews.find((fr) => fr.id === r.id);
        return updated ?? r;
      }),
    };

    await storage.set(
      STORAGE_KEYS.CURRENT_ANALYSIS as keyof import('@/types').StorageSchema,
      mergedResult as never,
    );

    // 재분석 완료 상태 갱신
    saveCrawlState({
      phase: 'done',
      pages: 0,
      reviews: currentAnalysis.reviews.length,
      chunksComplete: 0,
      totalChunks: 0,
      updatedAt: Date.now(),
    });
    chrome.action.setBadgeText({ text: '' });

    broadcastAnalysisComplete(mergedResult);
  } catch (err) {
    console.error('[ReviewPick] 재분석 오류:', err);
    saveCrawlState({
      phase: 'error',
      pages: 0,
      reviews: 0,
      chunksComplete: 0,
      totalChunks: 0,
      errorMsg: err instanceof Error ? err.message : '재분석 중 오류 발생',
      updatedAt: Date.now(),
    });
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#F04452' });

    const errMsg = err instanceof Error ? err.message : '재분석 중 오류가 발생했습니다.';
    chrome.runtime.sendMessage({ action: 'ANALYSIS_ERROR', message: errMsg } as ExtensionMessage).catch(() => {});
  }
}

// ─── 비교 모드 상품 추가 ─────────────────────────────────────────────────

async function handleCompareAdd(url: string) {
  // 현재 분석 결과를 ComparisonSession에 추가 저장
  const currentAnalysis = await storage.get(
    STORAGE_KEYS.CURRENT_ANALYSIS as keyof import('@/types').StorageSchema,
  ) as AnalysisResult | null;

  if (currentAnalysis) {
    const existing = (await storage.get(
      STORAGE_KEYS.COMPARISON_SESSIONS as keyof import('@/types').StorageSchema,
    ) as import('@/types').ComparisonSession[] | null) ?? [];

    // 새 세션 생성 (기존 분석을 첫 번째 상품으로 등록)
    const newSession: import('@/types').ComparisonSession = {
      id: uuidv4(),
      createdAt: new Date().toISOString(),
      products: [currentAnalysis],
    };

    await storage.set(
      STORAGE_KEYS.COMPARISON_SESSIONS as keyof import('@/types').StorageSchema,
      [...existing, newSession] as never,
    );
  }

  // 비교 대상 URL을 새 탭에서 열어 크롤링 트리거 (content script가 START_CRAWL 대기)
  chrome.tabs.create({ url, active: true });
}

// ─── 유틸 함수들 ─────────────────────────────────────────────────────────

function chunkArray<T>(arr: T[], size: number): T[][] {
  const result: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    result.push(arr.slice(i, i + size));
  }
  return result;
}

function broadcastProgress(chunksComplete: number, totalChunks: number) {
  const msg: ExtensionMessage = {
    action: 'ANALYSIS_PROGRESS',
    chunksComplete,
    totalChunks,
  };
  chrome.runtime.sendMessage(msg).catch(() => {});
}

function saveCrawlState(state: CrawlState) {
  chrome.storage.local.set({ [STORAGE_KEYS.CRAWL_STATE]: state }, () => {
    if (chrome.runtime.lastError) {
      console.error('[ReviewPick] crawlState 저장 실패:', chrome.runtime.lastError.message);
    }
  });
}

function broadcastAnalysisComplete(result: AnalysisResult) {
  const msg: ExtensionMessage = { action: 'ANALYSIS_COMPLETE', result };
  chrome.runtime.sendMessage(msg).catch(() => {});
}

/**
 * GeminiAnalysisChunk + 원본 리뷰 → AnalysisResult 구성
 */
function buildAnalysisResult(
  gemini: GeminiAnalysisChunk,
  reviews: RawReview[],
  productName: string,
  productUrl: string,
): AnalysisResult {
  const total = gemini.sentiment.positiveCount + gemini.sentiment.negativeCount + gemini.sentiment.neutralCount;

  // reviewTags를 인덱스로 매핑
  const tagMap = new Map<number, { sentiment: SentimentLabel; keywords: string[] }>();
  for (const tag of gemini.reviewTags) {
    tagMap.set(tag.reviewIndex - 1, { // 0-based로 변환
      sentiment: tag.sentiment,
      keywords: tag.keywords,
    });
  }

  const taggedReviews: TaggedReview[] = reviews.map((r, i) => ({
    ...r,
    sentiment: tagMap.get(i)?.sentiment ?? 'neutral',
    keywords: tagMap.get(i)?.keywords ?? [],
  }));

  // 마인드맵 루트 노드 구성
  const mindmapRoot = buildMindmapRoot(gemini, taggedReviews, productName);

  return {
    id: uuidv4(),
    productName,
    productUrl,
    platform: reviews[0]?.platform ?? 'coupang',
    scrapedAt: new Date().toISOString(),
    totalReviews: reviews.length,
    sentiment: {
      positiveCount: gemini.sentiment.positiveCount,
      negativeCount: gemini.sentiment.negativeCount,
      neutralCount: gemini.sentiment.neutralCount,
      positivePercent: total > 0 ? Math.round((gemini.sentiment.positiveCount / total) * 100) : 0,
      negativePercent: total > 0 ? Math.round((gemini.sentiment.negativeCount / total) * 100) : 0,
    },
    summary: gemini.summary,
    keywords: gemini.keywords,
    reviews: taggedReviews,
    mindmapRoot,
  };
}

/**
 * 키워드 데이터로 마인드맵 트리 구성
 * - 최상위 노드 수: 리뷰 수에 비례해 동적 결정 (최소 3, 최대 8)
 * - 2레벨 연관 키워드 중 count=0인 노드는 필터링
 */
function buildMindmapRoot(
  gemini: GeminiAnalysisChunk,
  reviews: TaggedReview[],
  productName: string,
): MindmapNode {
  // 키워드와 연관된 리뷰 인덱스 매핑
  const keywordReviewMap = new Map<string, number[]>();
  reviews.forEach((r, i) => {
    r.keywords.forEach((kw) => {
      const existing = keywordReviewMap.get(kw) ?? [];
      existing.push(i);
      keywordReviewMap.set(kw, existing);
    });
  });

  // 리뷰 수에 비례한 동적 최상위 노드 수 결정
  // 리뷰 10개당 1개 노드, 최소 3개, 최대 8개
  const dynamicTopCount = Math.min(8, Math.max(3, Math.floor(reviews.length / 10)));
  const kwSentimentMap = new Map(gemini.keywords.map((k) => [k.word, k.sentiment]));
  const topKeywords = gemini.keywords.slice(0, dynamicTopCount);

  const children: MindmapNode[] = topKeywords.map((kw) => {
    // 연관 키워드 → 2레벨 노드 (최대 4개, count > 0인 것만)
    const subChildren: MindmapNode[] = kw.relatedKeywords
      .slice(0, 4)
      .map((related) => ({
        id: `kw-${related}`,
        label: related,
        sentiment: kwSentimentMap.get(related) ?? 'neutral',
        count: keywordReviewMap.get(related)?.length ?? 0,
        relatedReviewIndices: keywordReviewMap.get(related) ?? [],
      }))
      .filter((node) => node.count > 0); // count=0 노드 제거

    const reviewIndices = keywordReviewMap.get(kw.word) ?? [];
    return {
      id: `kw-${kw.word}`,
      label: kw.word,
      sentiment: kw.sentiment,
      // relatedReviewIndices 길이와 일치시킴 → 원 안 숫자 = 클릭 시 나오는 리뷰 수
      count: reviewIndices.length,
      children: subChildren.length > 0 ? subChildren : undefined,
      relatedReviewIndices: reviewIndices,
    };
  });

  return {
    id: 'root',
    label: productName,
    sentiment: 'neutral',
    count: reviews.length,
    children,
    relatedReviewIndices: reviews.map((_, i) => i),
  };
}
