// ── SSE replay 헬퍼 — route.ts 에서 추출한 순수 함수 ────────────────────────
// - readLastLines: content 문자열에서 마지막 n줄 반환
// - parseEventLine: JSON 파싱 실패 시 null (silent skip 보장)

/**
 * 줄바꿈으로 분할한 뒤 빈 줄을 제거하고 마지막 n줄만 반환한다.
 * route.ts `else` 분기의 `lines.slice(-REPLAY_N)` 로직과 동일.
 */
export function readLastLines(content: string, n: number): string[] {
  return content.split("\n").filter(Boolean).slice(-n);
}

/**
 * SSE 이벤트 라인을 JSON 파싱한다.
 * 손상된 라인이면 null 을 반환해 silent skip 을 가능하게 한다.
 */
export function parseEventLine(line: string): { id?: string } | null {
  try {
    return JSON.parse(line) as { id?: string };
  } catch {
    return null;
  }
}
