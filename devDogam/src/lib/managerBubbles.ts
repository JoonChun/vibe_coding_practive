import type { AgentEvent } from "@/types/events";

export const BUBBLE_EVENT_TYPES = new Set([
  "agent_start",
  "agent_end",
  "agent_dispatch",
  "agent_message",
]);

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

export function deriveManagerBubbles(
  events: AgentEvent[]
): Record<string, string> {
  const map: Record<string, string> = {};
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (!BUBBLE_EVENT_TYPES.has(e.type)) continue;
    const msg = e.message?.trim() || synthesizeBubbleMessage(e.type);
    if (!msg) continue;
    if (!map[e.agentName]) map[e.agentName] = msg;
  }
  return map;
}
