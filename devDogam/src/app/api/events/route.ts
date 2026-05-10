// ── SSE API route — events/stream.jsonl 감시 (PHASE-1-SPEC.md §3·§4, M2.2) ──
// §12-2 채택안: chokidar v3 + usePolling:true, interval:300 (WSL2 inotify 우회)

import { NextRequest } from "next/server";
import chokidar from "chokidar";
import { promises as fs } from "fs";
import { resolve } from "path";

export const dynamic = "force-dynamic";
export const runtime = "nodejs"; // chokidar는 Node 런타임 필수

// process.cwd()는 dev 서버 기동 시 devDogam/ 기준
const STREAM_PATH = resolve(process.cwd(), "events/stream.jsonl");

export async function GET(request: NextRequest) {
  const lastEventId = request.headers.get("last-event-id");

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      let lastByteOffset = 0;
      // last-event-id 없으면 신규 이벤트만 전송
      let pastLastId = !lastEventId;

      // ── last-event-id 있으면: 파일 처음부터 읽어서 해당 id 이후만 push ────
      if (lastEventId) {
        try {
          const content = await fs.readFile(STREAM_PATH, "utf-8");
          const lines = content.split("\n").filter(Boolean);
          for (const line of lines) {
            try {
              const event = JSON.parse(line) as { id?: string };
              if (pastLastId) {
                controller.enqueue(
                  encoder.encode(`id: ${event.id}\ndata: ${line}\n\n`)
                );
              } else if (event.id === lastEventId) {
                pastLastId = true;
              }
            } catch {
              // malformed line — 무시
            }
          }
          const stat = await fs.stat(STREAM_PATH);
          lastByteOffset = stat.size;
        } catch {
          // 파일 없음 — 무시, lastByteOffset = 0 유지
        }
      } else {
        // last-event-id 없으면 현재 파일 끝 위치부터 신규 이벤트만 감시
        try {
          const stat = await fs.stat(STREAM_PATH);
          lastByteOffset = stat.size;
        } catch {
          // 파일 아직 없음 — OK, 0에서 시작
        }
      }

      // ── chokidar 파일 감시 (WSL2 inotify 불안정 → usePolling) ─────────────
      const watcher = chokidar.watch(STREAM_PATH, {
        usePolling: true,
        interval: 300,
        persistent: true,
        awaitWriteFinish: false,
        // 아직 존재하지 않는 파일도 감시 가능하도록
        ignoreInitial: false,
      });

      const pushNewLines = async () => {
        try {
          const stat = await fs.stat(STREAM_PATH);
          if (stat.size <= lastByteOffset) return;

          const fd = await fs.open(STREAM_PATH, "r");
          const buf = Buffer.alloc(stat.size - lastByteOffset);
          await fd.read(buf, 0, buf.length, lastByteOffset);
          await fd.close();
          lastByteOffset = stat.size;

          const newLines = buf.toString("utf-8").split("\n").filter(Boolean);
          for (const line of newLines) {
            try {
              const event = JSON.parse(line) as { id?: string };
              controller.enqueue(
                encoder.encode(`id: ${event.id ?? ""}\ndata: ${line}\n\n`)
              );
            } catch {
              // malformed line — skip
            }
          }
        } catch {
          // 파일 사라짐 or 읽기 실패 — 다음 add/change 이벤트 기다림
        }
      };

      watcher.on("add", pushNewLines);
      watcher.on("change", pushNewLines);

      // ── 초기 연결 확인용 즉시 ping ────────────────────────────────────────
      // Turbopack/프록시 버퍼 flush 강제, curl 시험 시 즉각 응답 확인 가능
      try {
        controller.enqueue(encoder.encode(": ping\n\n"));
      } catch {
        // 이미 닫힌 경우 무시
      }

      // ── 클라이언트 연결 종료 시 정리 ─────────────────────────────────────
      const cleanup = () => {
        watcher.close().catch(() => {});
        clearInterval(pingTimer);
        try {
          controller.close();
        } catch {
          // 이미 닫힌 경우 무시
        }
      };

      request.signal.addEventListener("abort", cleanup, { once: true });

      // ── keep-alive 핑 (30초) — 프록시 timeout 방지 ─────────────────────
      const pingTimer = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(": ping\n\n"));
        } catch {
          clearInterval(pingTimer);
        }
      }, 30_000);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
