import type { AgentEvent } from "@/types/events";

export const BUBBLE_EVENT_TYPES = new Set([
  "agent_start",
  "agent_end",
  "agent_dispatch",
  "agent_message",
]);

/** agent_end 말풍선 자동 사라짐 시간 (ms) */
export const AGENT_END_TTL_MS = 10_000;

export function synthesizeBubbleMessage(type: string): string {
  switch (type) {
    case "agent_start":
      return "작업을 시작합니다.";
    case "agent_end":
      return "작업을 마쳤습니다.";
    case "agent_dispatch":
      return "명을 받습니다.";
    default:
      return "";
  }
}

/**
 * 각 에이전트의 가장 최근 말풍선 메시지 derive.
 *
 * @param events 이벤트 배열
 * @param now    현재 시각 (ms). agent_end TTL 판단용.
 *               서버 SSR 시 0으로 호출하면 fade 안 적용됨 (hydration 안전).
 */
export function deriveManagerBubbles(
  events: AgentEvent[],
  now: number = Date.now()
): Record<string, string> {
  const map: Record<string, string> = {};

  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (!BUBBLE_EVENT_TYPES.has(e.type)) continue;
    // 이 에이전트의 *최신 bubble 이벤트*만 처리 — 이미 결정되면 skip
    if (map[e.agentName]) continue;

    // agent_end 가 10초 경과 시 → 이 이벤트만 skip, 이전 이벤트(agent_message 등)로 fall back
    // 이전 코드의 faded Set은 해당 에이전트의 *모든* 과거 이벤트를 차단해서
    // 매니저 말풍선이 영원히 안 보이는 버그가 있었음. 수정.
    if (e.type === "agent_end" && now - e.timestamp > AGENT_END_TTL_MS) {
      continue;
    }

    const msg = e.message?.trim() || synthesizeBubbleMessage(e.type);
    if (!msg) continue;
    map[e.agentName] = msg;
  }
  return map;
}
