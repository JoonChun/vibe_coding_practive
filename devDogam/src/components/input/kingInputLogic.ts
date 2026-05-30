// ── KingInput 순수 로직 ───────────────────────────────────────────────────────
// 컴포넌트와 분리 — vitest node 환경에서 테스트 가능.

/**
 * API 에러 코드를 한국어 메시지로 변환.
 * 군관이 이 함수를 별도 테스트할 수 있도록 export.
 */
export function mapErrorToMessage(code: string | undefined): string {
  switch (code) {
    case "no_dogam_session":
      return "도감 세션이 열려 있지 않습니다. start-reels-session.sh를 먼저 실행하세요";
    case "tmux_not_found":
      return "tmux를 찾을 수 없습니다";
    case "rate_limited":
      return "명을 너무 빠르게 내리셨습니다. 잠시 후 다시 시도하세요";
    case "prompt_too_long":
      return "명이 너무 깁니다 (최대 2000자)";
    case "send_keys_failed":
      return "세션 전달에 실패하였습니다";
    case "empty_prompt":
      return "명을 입력해 주십시오";
    case "invalid_body":
      return "요청 형식이 잘못되었습니다";
    default:
      return "알 수 없는 오류가 발생하였습니다";
  }
}

/** sendKingPrompt의 반환 타입 */
export type SendResult = { ok: true } | { ok: false; message: string };

/**
 * /api/king-prompt 로 명을 전달하는 fetch 래퍼.
 * fetchImpl 주입으로 vitest에서 목(mock) 대체 가능.
 */
export async function sendKingPrompt(
  prompt: string,
  fetchImpl: typeof fetch = fetch
): Promise<SendResult> {
  let res: Response;
  try {
    res = await fetchImpl("/api/king-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
  } catch {
    // 네트워크 오류 — 서버 연결 불가
    return { ok: false, message: "서버에 연결할 수 없습니다" };
  }

  if (res.ok) {
    return { ok: true };
  }

  // 서버 측 오류 코드 파싱
  let errorCode: string | undefined;
  try {
    const data = (await res.json()) as { error?: string };
    errorCode = data.error;
  } catch {
    // JSON 파싱 실패 — 기본 메시지 반환
  }

  return { ok: false, message: mapErrorToMessage(errorCode) };
}
