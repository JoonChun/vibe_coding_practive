import { type NextRequest } from "next/server";
import { spawnSync } from "node:child_process";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// 모듈 레벨 rate limit 상태
let lastSentAt = 0;

export async function POST(request: NextRequest) {
  // ── 입력 검증 ──────────────────────────────────────────────────────────────
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "invalid_body" }, { status: 400 });
  }

  if (
    typeof body !== "object" ||
    body === null ||
    !("prompt" in body) ||
    typeof (body as Record<string, unknown>).prompt !== "string"
  ) {
    return Response.json({ error: "empty_prompt" }, { status: 400 });
  }

  const prompt = ((body as Record<string, unknown>).prompt as string).trim();
  if (prompt.length === 0) {
    return Response.json({ error: "empty_prompt" }, { status: 400 });
  }
  if (prompt.length > 2000) {
    return Response.json({ error: "prompt_too_long" }, { status: 413 });
  }

  // ── Rate limit ─────────────────────────────────────────────────────────────
  if (Date.now() - lastSentAt < 1000) {
    return Response.json({ error: "rate_limited" }, { status: 429 });
  }

  // ── tmux 설치 확인 ─────────────────────────────────────────────────────────
  const tmuxCheck = spawnSync("tmux", ["-V"]);
  if (tmuxCheck.status !== 0) {
    return Response.json({ error: "tmux_not_found" }, { status: 503 });
  }

  // ── dogam- 세션 탐지 ───────────────────────────────────────────────────────
  const lsResult = spawnSync("tmux", ["ls", "-F", "#{session_name}"]);
  if (lsResult.status !== 0) {
    return Response.json({ error: "no_dogam_session" }, { status: 503 });
  }

  const sessions = lsResult.stdout
    .toString("utf-8")
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.startsWith("dogam-"))
    .sort();

  if (sessions.length === 0) {
    return Response.json({ error: "no_dogam_session" }, { status: 503 });
  }

  const sessionName = sessions[sessions.length - 1];

  // ── 텍스트 전송 (-l: 리터럴, shell 해석 없음) ──────────────────────────────
  const sendText = spawnSync("tmux", [
    "send-keys",
    "-t",
    `${sessionName}:0.0`,
    "-l",
    prompt,
  ]);
  if (sendText.status !== 0) {
    return Response.json({ error: "send_keys_failed" }, { status: 500 });
  }

  // ── Enter 별도 전송 ────────────────────────────────────────────────────────
  const sendEnter = spawnSync("tmux", [
    "send-keys",
    "-t",
    `${sessionName}:0.0`,
    "Enter",
  ]);
  if (sendEnter.status !== 0) {
    return Response.json({ error: "send_keys_failed" }, { status: 500 });
  }

  // 성공 시 rate limit 타임스탬프 갱신
  lastSentAt = Date.now();

  return Response.json({ success: true, taskId: null }, { status: 200 });
}
