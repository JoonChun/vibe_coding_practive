// ─── 플랫폼 ────────────────────────────────────────────────────────────────

export type Platform = 'coupang' | 'naver';

// ─── 크롤링 원본 데이터 ────────────────────────────────────────────────────

export interface RawReview {
  id: string;           // `${platform}-${index}`
  platform: Platform;
  text: string;
  rating: number;       // 1–5
  author: string;
  date: string;
  productId: string;    // URL에서 추출
}

// ─── AI 태깅 후 리뷰 ──────────────────────────────────────────────────────

export type SentimentLabel = 'positive' | 'negative' | 'neutral';

export interface TaggedReview extends RawReview {
  sentiment: SentimentLabel;
  keywords: string[];
}

// ─── 마인드맵 노드 (D3) ────────────────────────────────────────────────────

export interface MindmapNode {
  id: string;
  label: string;
  sentiment: SentimentLabel;
  count: number;
  children?: MindmapNode[];
  relatedReviewIndices: number[];  // TaggedReview 배열의 인덱스
}

// ─── Gemini API 응답 스키마 ───────────────────────────────────────────────

export interface GeminiAnalysisChunk {
  summary: {
    positive: string;
    negative: string;
    overall: string;
    marketingInsights: string[];
  };
  sentiment: {
    positiveCount: number;
    negativeCount: number;
    neutralCount: number;
  };
  keywords: Array<{
    word: string;
    count: number;
    sentiment: SentimentLabel;
    relatedKeywords: string[];
  }>;
  reviewTags: Array<{
    reviewIndex: number;      // 1-based (Gemini 프롬프트의 번호와 일치)
    sentiment: SentimentLabel;
    keywords: string[];
  }>;
}

// ─── 전체 분석 결과 (chrome.storage 저장 단위) ────────────────────────────

export interface AnalysisResult {
  id: string;
  productName: string;
  productUrl: string;
  platform: Platform;
  scrapedAt: string;           // ISO timestamp
  totalReviews: number;
  sentiment: {
    positiveCount: number;
    negativeCount: number;
    neutralCount: number;
    positivePercent: number;
    negativePercent: number;
  };
  summary: {
    positive: string;
    negative: string;
    overall: string;
    marketingInsights: string[];
  };
  keywords: Array<{
    word: string;
    count: number;
    sentiment: SentimentLabel;
    relatedKeywords: string[];
  }>;
  reviews: TaggedReview[];
  mindmapRoot: MindmapNode;
}

// ─── 비교 모드 ────────────────────────────────────────────────────────────

export interface ComparisonSession {
  id: string;
  createdAt: string;
  products: AnalysisResult[];
}

// ─── 크롤링 진행 상태 (popup 재오픈 시 복원용) ───────────────────────────

export interface CrawlState {
  phase: 'crawling' | 'analyzing' | 'done' | 'error';
  pages: number;
  reviews: number;
  chunksComplete: number;
  totalChunks: number;
  errorMsg?: string;
  updatedAt: number; // Date.now()
}

// ─── chrome.storage 스키마 ────────────────────────────────────────────────

export interface StorageSchema {
  currentAnalysis: AnalysisResult | null;
  comparisonSessions: ComparisonSession[];
  geminiApiKey: string;
  userPreferences: {
    defaultChunkSize: number;
    minDelay: number;
    maxDelay: number;
  };
  crawlState: CrawlState;
  maxReviews: number;
}

// ─── 확장 프로그램 메시지 타입 ────────────────────────────────────────────

export type ExtensionMessage =
  | { action: 'START_CRAWL'; maxReviews: number }
  | { action: 'CRAWL_PROGRESS'; pagesScraped: number; totalReviews: number }
  | { action: 'CRAWL_COMPLETE'; reviews: RawReview[]; productName: string; productUrl: string }
  | { action: 'ANALYSIS_PROGRESS'; chunksComplete: number; totalChunks: number }
  | { action: 'ANALYSIS_COMPLETE'; result: AnalysisResult }
  | { action: 'ANALYSIS_ERROR'; message: string }
  | { action: 'RE_ANALYZE'; keyword: string }
  | { action: 'COMPARE_ADD'; url: string };

// ─── 플랫폼 선택자 설정 ───────────────────────────────────────────────────

export interface PlatformSelectorConfig {
  reviewContainer: string;   // 개별 리뷰 컨테이너
  reviewText: string;        // 리뷰 본문 텍스트
  rating: string;            // 별점 요소
  author: string;            // 작성자
  date: string;              // 작성일
  nextPageButton: string;    // 다음 페이지 버튼 (네이버 페이지네이션)
  scrollTarget: string;      // 스크롤 대상 요소 (쿠팡 무한 스크롤)
}
