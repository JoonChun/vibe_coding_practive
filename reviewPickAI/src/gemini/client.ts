import type { RawReview, GeminiAnalysisChunk } from '@/types';
import { GEMINI_MODEL, GEMINI_API_BASE } from '@/constants';
import { SYSTEM_PROMPT, buildUserPrompt } from './prompts';

export class GeminiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
  ) {
    super(message);
    this.name = 'GeminiError';
  }
}

/** Rate limit 및 서버 오류 시 지수 백오프 재시도 최대 횟수 */
const MAX_RETRIES = 3;

/** 초기 백오프 대기 시간 (ms) */
const BACKOFF_BASE_MS = 2000;

/**
 * 지정된 ms만큼 대기하는 유틸리티
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Gemini REST API를 통해 리뷰 청크를 분석
 * 429(rate limit) 및 5xx(서버 오류) 발생 시 지수 백오프로 최대 MAX_RETRIES 회 재시도
 */
export async function analyzeReviews(
  reviews: RawReview[],
  apiKey: string,
  offset = 0,
): Promise<GeminiAnalysisChunk> {
  const url = `${GEMINI_API_BASE}/${GEMINI_MODEL}:generateContent?key=${apiKey}`;

  const body = {
    systemInstruction: {
      parts: [{ text: SYSTEM_PROMPT }],
    },
    contents: [
      {
        role: 'user',
        parts: [{ text: buildUserPrompt(reviews, offset) }],
      },
    ],
    generationConfig: {
      temperature: 0.1,
      topP: 0.8,
      responseMimeType: 'application/json',
    },
  };

  let lastError: GeminiError | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      const waitMs = BACKOFF_BASE_MS * Math.pow(2, attempt - 1);
      console.warn(`[ReviewPick] Gemini 재시도 ${attempt}/${MAX_RETRIES} — ${waitMs}ms 대기 (이전 오류: ${lastError?.statusCode})`);
      await sleep(waitMs);
    }

    let response: Response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (networkErr) {
      lastError = new GeminiError(
        `Gemini 네트워크 오류: ${networkErr instanceof Error ? networkErr.message : String(networkErr)}`,
      );
      continue; // 네트워크 오류도 재시도
    }

    if (!response.ok) {
      const errText = await response.text().catch(() => '');
      const isRetryable = response.status === 429 || response.status >= 500;
      lastError = new GeminiError(
        `Gemini API 오류 ${response.status}: ${errText}`,
        response.status,
      );
      if (isRetryable && attempt < MAX_RETRIES) {
        continue; // 재시도 가능한 오류면 계속
      }
      throw lastError;
    }

    const data = await response.json();
    const rawText: string =
      data?.candidates?.[0]?.content?.parts?.[0]?.text ?? '';

    return parseGeminiResponse(rawText);
  }

  throw lastError ?? new GeminiError('Gemini API 요청 실패 (알 수 없는 오류)');
}

/**
 * Gemini 응답 텍스트를 GeminiAnalysisChunk로 파싱
 * 코드 펜스 제거 후 JSON.parse 시도, 실패 시 GeminiError를 throw
 */
function parseGeminiResponse(rawText: string): GeminiAnalysisChunk {
  // 코드 펜스 제거
  const cleaned = rawText
    .replace(/```json\s*/gi, '')
    .replace(/```\s*/gi, '')
    .trim();

  if (!cleaned) {
    throw new GeminiError('Gemini 응답이 비어 있습니다.');
  }

  try {
    return JSON.parse(cleaned) as GeminiAnalysisChunk;
  } catch (e) {
    throw new GeminiError(
      `Gemini 응답 JSON 파싱 실패: ${e instanceof Error ? e.message : String(e)}\n원본: ${rawText.slice(0, 200)}`,
    );
  }
}

/**
 * 여러 청크의 GeminiAnalysisChunk를 하나로 병합
 */
export function mergeChunks(chunks: GeminiAnalysisChunk[]): GeminiAnalysisChunk {
  if (chunks.length === 0) {
    throw new GeminiError('병합할 청크가 없습니다.');
  }
  if (chunks.length === 1) return chunks[0];

  // sentiment 합산
  const sentiment = chunks.reduce(
    (acc, c) => ({
      positiveCount: acc.positiveCount + c.sentiment.positiveCount,
      negativeCount: acc.negativeCount + c.sentiment.negativeCount,
      neutralCount: acc.neutralCount + c.sentiment.neutralCount,
    }),
    { positiveCount: 0, negativeCount: 0, neutralCount: 0 },
  );

  // keywords 중복 제거 + count 합산
  const keywordMap = new Map<
    string,
    GeminiAnalysisChunk['keywords'][number]
  >();
  for (const chunk of chunks) {
    for (const kw of chunk.keywords) {
      const existing = keywordMap.get(kw.word);
      if (existing) {
        existing.count += kw.count;
        const relatedSet = new Set([
          ...existing.relatedKeywords,
          ...kw.relatedKeywords,
        ]);
        existing.relatedKeywords = Array.from(relatedSet);
      } else {
        keywordMap.set(kw.word, { ...kw });
      }
    }
  }

  // reviewTags 합산 (각 청크는 이미 offset-adjusted된 인덱스 사용)
  const reviewTags = chunks.flatMap((c) => c.reviewTags);

  // summary 병합: 각 청크의 positive/negative/overall을 구분자로 이어붙이고
  // marketingInsights는 중복 제거 후 최대 5개 보존
  const summary = {
    positive: chunks.map((c) => c.summary.positive).filter(Boolean).join(' / '),
    negative: chunks.map((c) => c.summary.negative).filter(Boolean).join(' / '),
    overall: chunks.map((c) => c.summary.overall).filter(Boolean).join(' / '),
    marketingInsights: Array.from(
      new Set(chunks.flatMap((c) => c.summary.marketingInsights)),
    ).slice(0, 5),
  };

  return {
    summary,
    sentiment,
    keywords: Array.from(keywordMap.values()).sort((a, b) => b.count - a.count),
    reviewTags,
  };
}
