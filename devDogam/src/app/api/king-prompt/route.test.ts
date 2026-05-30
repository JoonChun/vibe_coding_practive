// ── /api/king-prompt POST 핸들러 단위 시험 ────────────────────────────────────
// 목적:
//   route.ts 의 10개 케이스를 spawnSync mock으로 격리 검증.
//   환경: vitest (node). DOM 없음.
//
// 전략:
//   - node:child_process 전체를 vi.mock으로 대체
//   - rate limit은 모듈 레벨 상태이므로 매 시험 전 vi.resetModules() + 재import
//   - 시간 의존 케이스(TC-R07)는 vi.useFakeTimers로 Date.now 제어

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── spawnSync 결과 헬퍼 ────────────────────────────────────────────────────────
function makeSpawnResult(status: number, stdout = "") {
  return {
    status,
    stdout: Buffer.from(stdout),
    stderr: Buffer.from(""),
    pid: 1,
    output: [],
    signal: null,
    error: undefined,
  };
}

// ── spawnSync 순서대로 응답 지정 헬퍼 ─────────────────────────────────────────
// spawnSync는 호출 순서대로 mockReturnValueOnce로 제어한다.
// 정상 경로: tmux -V (ok), tmux ls (ok+sessions), send-keys -l (ok), send-keys Enter (ok)
function setupNormalSpawn(
  spawnSyncMock: ReturnType<typeof vi.fn>,
  session = "dogam-main"
) {
  spawnSyncMock
    .mockReturnValueOnce(makeSpawnResult(0))                     // tmux -V
    .mockReturnValueOnce(makeSpawnResult(0, `${session}\n`))      // tmux ls
    .mockReturnValueOnce(makeSpawnResult(0))                     // send-keys -l
    .mockReturnValueOnce(makeSpawnResult(0));                    // send-keys Enter
}

// ── 공통 Request 생성 헬퍼 ────────────────────────────────────────────────────
function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/king-prompt", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

// ── 각 시험 전 모듈 격리 (rate limit 리셋) ────────────────────────────────────
// vi.resetModules() 로 모듈 캐시를 비우고 매번 새 인스턴스를 동적 import한다.

describe("/api/king-prompt POST 핸들러", () => {
  // spawnSync mock 참조 — 각 beforeEach에서 재설정
  let spawnSyncMock: ReturnType<typeof vi.fn>;
  let POST: (req: Request) => Promise<Response>;

  beforeEach(async () => {
    vi.resetModules();

    // node:child_process를 빈 mock으로 교체
    spawnSyncMock = vi.fn();
    vi.doMock("node:child_process", () => ({
      spawnSync: spawnSyncMock,
    }));

    // 모듈 재import (rate limit 상태 초기화됨)
    const mod = await import("./route");
    POST = mod.POST as unknown as (req: Request) => Promise<Response>;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  // ── TC-R01: 정상 흐름 ─────────────────────────────────────────────────────
  it("TC-R01: 정상 prompt → 200 { success: true, taskId: null }", async () => {
    setupNormalSpawn(spawnSyncMock);

    const res = await POST(makeRequest({ prompt: "BMI 추가해줘" }));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual({ success: true, taskId: null });
  });

  // ── TC-R02: 빈 문자열 ─────────────────────────────────────────────────────
  it("TC-R02: 빈 문자열 prompt → 400 { error: 'empty_prompt' }", async () => {
    const res = await POST(makeRequest({ prompt: "" }));
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body).toEqual({ error: "empty_prompt" });
    // spawnSync는 호출되지 않아야 함 (입력 검증 단계에서 종료)
    expect(spawnSyncMock).not.toHaveBeenCalled();
  });

  // ── TC-R03: 2001자 prompt → 413 ───────────────────────────────────────────
  it("TC-R03: 2001자 prompt → 413 { error: 'prompt_too_long' }", async () => {
    const longPrompt = "가".repeat(2001);
    const res = await POST(makeRequest({ prompt: longPrompt }));
    const body = await res.json();

    expect(res.status).toBe(413);
    expect(body).toEqual({ error: "prompt_too_long" });
    expect(spawnSyncMock).not.toHaveBeenCalled();
  });

  // ── TC-R04: tmux -V 실패 → 503 tmux_not_found ────────────────────────────
  it("TC-R04: tmux -V status 1 → 503 { error: 'tmux_not_found' }", async () => {
    spawnSyncMock.mockReturnValueOnce(makeSpawnResult(1)); // tmux -V 실패

    const res = await POST(makeRequest({ prompt: "테스트" }));
    const body = await res.json();

    expect(res.status).toBe(503);
    expect(body).toEqual({ error: "tmux_not_found" });
    // tmux ls 이후는 호출 안 됨
    expect(spawnSyncMock).toHaveBeenCalledTimes(1);
  });

  // ── TC-R05: dogam-* 세션 없음 → 503 no_dogam_session ─────────────────────
  it("TC-R05: tmux ls에 dogam-* 없음 → 503 { error: 'no_dogam_session' }", async () => {
    spawnSyncMock
      .mockReturnValueOnce(makeSpawnResult(0))                   // tmux -V ok
      .mockReturnValueOnce(makeSpawnResult(0, "other-session\n")); // tmux ls (dogam- 없음)

    const res = await POST(makeRequest({ prompt: "테스트" }));
    const body = await res.json();

    expect(res.status).toBe(503);
    expect(body).toEqual({ error: "no_dogam_session" });
  });

  // ── TC-R06: send-keys -l 실패 → 500 send_keys_failed ────────────────────
  it("TC-R06: send-keys -l status 1 → 500 { error: 'send_keys_failed' }", async () => {
    spawnSyncMock
      .mockReturnValueOnce(makeSpawnResult(0))                   // tmux -V ok
      .mockReturnValueOnce(makeSpawnResult(0, "dogam-main\n"))   // tmux ls ok
      .mockReturnValueOnce(makeSpawnResult(1));                  // send-keys -l 실패

    const res = await POST(makeRequest({ prompt: "테스트" }));
    const body = await res.json();

    expect(res.status).toBe(500);
    expect(body).toEqual({ error: "send_keys_failed" });
    // Enter send-keys는 호출 안 됨
    expect(spawnSyncMock).toHaveBeenCalledTimes(3);
  });

  // ── TC-R07: 1초 내 2회 요청 → 두 번째 429 rate_limited ───────────────────
  it("TC-R07: 1초 내 연속 2회 요청 → 두 번째 429 { error: 'rate_limited' }", async () => {
    vi.useFakeTimers();
    const now = 1_700_000_000_000; // 고정 기준 시각
    vi.setSystemTime(now);

    // 첫 번째 요청 성공용 mock (4번 호출)
    setupNormalSpawn(spawnSyncMock);

    const res1 = await POST(makeRequest({ prompt: "첫 번째 명" }));
    expect(res1.status).toBe(200);

    // 500ms 경과 (1000ms 미만이므로 rate limit 유지)
    vi.advanceTimersByTime(500);

    const res2 = await POST(makeRequest({ prompt: "두 번째 명" }));
    const body2 = await res2.json();

    expect(res2.status).toBe(429);
    expect(body2).toEqual({ error: "rate_limited" });
  });

  // ── TC-R08: 특수문자 prompt — shell 미경유, 인자 그대로 전달 ──────────────
  it("TC-R08: 특수문자 prompt → 200 성공 + send-keys에 prompt 그대로 전달", async () => {
    const specialPrompt = "$;`'\"";
    setupNormalSpawn(spawnSyncMock);

    const res = await POST(makeRequest({ prompt: specialPrompt }));
    expect(res.status).toBe(200);

    // send-keys -l 호출 인자 검증: 배열 형태로 prompt가 그대로 전달
    // 3번째 spawnSync 호출 = send-keys 텍스트 전송
    const sendKeysCall = spawnSyncMock.mock.calls[2];
    expect(sendKeysCall[0]).toBe("tmux");
    // 인자 배열에 prompt가 포함되어야 함
    expect(sendKeysCall[1]).toContain(specialPrompt);
    // -l 플래그로 리터럴 전달 (shell 해석 없음)
    expect(sendKeysCall[1]).toContain("-l");
  });

  // ── TC-R09: body JSON 파싱 실패 → 400 invalid_body ───────────────────────
  it("TC-R09: 잘못된 JSON body → 400 { error: 'invalid_body' }", async () => {
    // JSON.stringify 우회 — 직접 텍스트 body 전송
    const req = new Request("http://localhost/api/king-prompt", {
      method: "POST",
      body: "이것은 JSON이 아닙니다",
      headers: { "Content-Type": "application/json" },
    });

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body).toEqual({ error: "invalid_body" });
    expect(spawnSyncMock).not.toHaveBeenCalled();
  });

  // ── TC-R10: send-keys 2회 호출 확인 + spawnSync 총 4회 ───────────────────
  it("TC-R10: 성공 경로에서 spawnSync 4회 호출 (-V, ls, send-keys -l, send-keys Enter)", async () => {
    setupNormalSpawn(spawnSyncMock);

    const res = await POST(makeRequest({ prompt: "호출 횟수 검증" }));
    expect(res.status).toBe(200);

    // 총 4회 호출
    expect(spawnSyncMock).toHaveBeenCalledTimes(4);

    // 1번째: tmux -V
    expect(spawnSyncMock.mock.calls[0]).toEqual(["tmux", ["-V"]]);

    // 2번째: tmux ls
    expect(spawnSyncMock.mock.calls[1][0]).toBe("tmux");
    expect(spawnSyncMock.mock.calls[1][1][0]).toBe("ls");

    // 3번째: send-keys -l (텍스트 전송)
    expect(spawnSyncMock.mock.calls[2][0]).toBe("tmux");
    expect(spawnSyncMock.mock.calls[2][1]).toContain("send-keys");
    expect(spawnSyncMock.mock.calls[2][1]).toContain("-l");

    // 4번째: send-keys Enter (Enter 별도 전송)
    expect(spawnSyncMock.mock.calls[3][0]).toBe("tmux");
    expect(spawnSyncMock.mock.calls[3][1]).toContain("send-keys");
    expect(spawnSyncMock.mock.calls[3][1]).toContain("Enter");
    // Enter 전송엔 -l 플래그 없음
    expect(spawnSyncMock.mock.calls[3][1]).not.toContain("-l");
  });
});
