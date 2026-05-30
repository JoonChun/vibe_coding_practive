// ── KingInput 순수 로직 단위 시험 ────────────────────────────────────────────
// 목적:
//   kingInputLogic.ts 의 mapErrorToMessage, sendKingPrompt 를 격리 검증.
//   환경: vitest (node). DOM 없음. fetch는 주입 mock으로 대체.

import { describe, it, expect, vi } from "vitest";
import { mapErrorToMessage, sendKingPrompt } from "./kingInputLogic";

// ── TC-K01 ~ TC-K04: mapErrorToMessage 검증 ──────────────────────────────────

describe("mapErrorToMessage — 에러 코드 → 한국어 메시지 변환", () => {

  // TC-K01: no_dogam_session 한국어 메시지
  it("TC-K01: 'no_dogam_session' → 도감 세션 안내 메시지", () => {
    const msg = mapErrorToMessage("no_dogam_session");
    // 한국어 포함 여부 + "도감" 또는 "세션" 키워드 포함
    expect(msg).toBeTruthy();
    expect(msg).toMatch(/도감|세션/);
  });

  // TC-K02: undefined → 알 수 없는 오류 기본 메시지
  it("TC-K02: undefined → '알 수 없는 오류가 발생하였습니다'", () => {
    const msg = mapErrorToMessage(undefined);
    expect(msg).toBe("알 수 없는 오류가 발생하였습니다");
  });

  // TC-K03: rate_limited → 빠르게 명령 관련 메시지
  it("TC-K03: 'rate_limited' → '명을 너무 빠르게...' 포함 메시지", () => {
    const msg = mapErrorToMessage("rate_limited");
    expect(msg).toMatch(/명을 너무 빠르게/);
  });

  // TC-K04: 8종 에러 코드 전부 한국어 매핑 존재 검증
  it("TC-K04: 8종 에러 코드 전부 비어있지 않은 한국어 메시지 반환", () => {
    // 구현 코드에 정의된 8종 에러 코드
    const errorCodes = [
      "no_dogam_session",
      "tmux_not_found",
      "rate_limited",
      "prompt_too_long",
      "send_keys_failed",
      "empty_prompt",
      "invalid_body",
      // 미등록 코드는 default 분기 — undefined 포함해 9번째로 검증
    ] as const;

    for (const code of errorCodes) {
      const msg = mapErrorToMessage(code);
      expect(msg, `${code} 의 매핑이 비어있음`).toBeTruthy();
      expect(msg, `${code} 의 매핑이 default 메시지와 같아선 안 됨`).not.toBe(
        "알 수 없는 오류가 발생하였습니다"
      );
    }

    // 미등록 코드는 default 메시지 반환
    const defaultMsg = mapErrorToMessage("completely_unknown_code");
    expect(defaultMsg).toBe("알 수 없는 오류가 발생하였습니다");
  });
});

// ── TC-K05 ~ TC-K08: sendKingPrompt 검증 ─────────────────────────────────────

describe("sendKingPrompt — fetch 래퍼 로직 검증", () => {

  // TC-K05: 200 응답 → { ok: true }
  it("TC-K05: fetchMock 200 + {} 반환 → { ok: true }", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    );

    const result = await sendKingPrompt("테스트 명령", fetchMock);

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  // TC-K06: 429 + rate_limited → { ok: false, message: "명을 너무 빠르게..." }
  it("TC-K06: fetchMock 429 + rate_limited → { ok: false, message 포함 }", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "rate_limited" }), { status: 429 })
    );

    const result = await sendKingPrompt("두 번째 명령", fetchMock);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toMatch(/명을 너무 빠르게/);
    }
  });

  // TC-K07: fetch throw → { ok: false, message: "서버에 연결할 수 없습니다" }
  it("TC-K07: fetchMock throw → { ok: false, message: '서버에 연결할 수 없습니다' }", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("Network Error"));

    const result = await sendKingPrompt("연결 실패 명령", fetchMock);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toBe("서버에 연결할 수 없습니다");
    }
  });

  // TC-K08: 특수문자 포함 prompt — body에 그대로 전달됐는지 확인
  it("TC-K08: 특수문자 prompt → fetch body에 JSON.stringify({ prompt }) 그대로 전달", async () => {
    const specialPrompt = "$;`'\"<script>";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true, taskId: null }), { status: 200 })
    );

    await sendKingPrompt(specialPrompt, fetchMock);

    // fetch 호출 인자 검증
    expect(fetchMock).toHaveBeenCalledOnce();
    const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(_url).toBe("/api/king-prompt");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual(
      expect.objectContaining({ "Content-Type": "application/json" })
    );

    // body가 JSON.stringify({ prompt: specialPrompt }) 와 동일한지 검증
    expect(init.body).toBe(JSON.stringify({ prompt: specialPrompt }));
  });
});
