// ── managerBubbles 단위 시험 ──────────────────────────────────────────────────
// deriveManagerBubbles, synthesizeBubbleMessage, BUBBLE_EVENT_TYPES 행위 검증

import { describe, it, expect } from "vitest";
import type { AgentEvent } from "@/types/events";
import {
  deriveManagerBubbles,
  synthesizeBubbleMessage,
  BUBBLE_EVENT_TYPES,
} from "./managerBubbles";

// ── 헬퍼 ─────────────────────────────────────────────────────────────────────
let seq = 0;
function makeEvent(
  type: AgentEvent["type"],
  agentName: string,
  message?: string
): AgentEvent {
  seq++;
  return {
    id: `b-${seq}`,
    timestamp: seq,
    type,
    agentName,
    taskId: "t-bubbles",
    ...(message !== undefined && { message }),
  };
}

// ── 테스트 ────────────────────────────────────────────────────────────────────

describe("deriveManagerBubbles", () => {
  it("빈 배열이면 빈 객체 반환", () => {
    expect(deriveManagerBubbles([])).toEqual({});
  });

  it("매니저 1인 agent_start 1건 — 합성 메시지 반환", () => {
    const result = deriveManagerBubbles([makeEvent("agent_start", "planner-dojeon")]);
    expect(result).toEqual({ "planner-dojeon": "작업을 시작합니다." });
  });

  it("매니저 2인 각 1건 — 둘 다 키 존재", () => {
    const events = [
      makeEvent("agent_start", "planner-dojeon"),
      makeEvent("agent_end", "implementer-yeongsil"),
    ];
    const result = deriveManagerBubbles(events);
    expect(result).toHaveProperty("planner-dojeon");
    expect(result).toHaveProperty("implementer-yeongsil");
  });

  it("같은 매니저 여러 이벤트 — 가장 최근(배열 끝) 이벤트 메시지만 보존", () => {
    const events = [
      makeEvent("agent_start", "planner-dojeon"),      // 오래된 것
      makeEvent("agent_end",   "planner-dojeon"),      // 최근 것
    ];
    const result = deriveManagerBubbles(events);
    // 역방향 순회이므로 마지막 이벤트(agent_end) 메시지가 채택됨
    expect(result["planner-dojeon"]).toBe("작업을 마쳤습니다.");
  });

  it("빈 message 필드 — synthesize 합성 메시지로 fallback", () => {
    const events = [makeEvent("agent_dispatch", "reviewer-sunsin", "")];
    const result = deriveManagerBubbles(events);
    expect(result["reviewer-sunsin"]).toBe("명을 받습니다.");
  });

  it("BUBBLE_EVENT_TYPES 외 이벤트(task_start 등) 무시", () => {
    const events = [
      makeEvent("task_start", "king"),
      makeEvent("task_end",   "king"),
    ];
    const result = deriveManagerBubbles(events);
    expect(result).toEqual({});
  });

  it("agent_message에 실제 텍스트 있으면 synthesize보다 우선", () => {
    const events = [makeEvent("agent_message", "ideator-yagyong", "새 기능 제안합니다.")];
    const result = deriveManagerBubbles(events);
    expect(result["ideator-yagyong"]).toBe("새 기능 제안합니다.");
  });
});

describe("synthesizeBubbleMessage", () => {
  it("agent_start → '작업을 시작합니다.'", () => {
    expect(synthesizeBubbleMessage("agent_start")).toBe("작업을 시작합니다.");
  });

  it("agent_end → '작업을 마쳤습니다.'", () => {
    expect(synthesizeBubbleMessage("agent_end")).toBe("작업을 마쳤습니다.");
  });

  it("agent_dispatch → '명을 받습니다.'", () => {
    expect(synthesizeBubbleMessage("agent_dispatch")).toBe("명을 받습니다.");
  });

  it("알 수 없는 타입 → 빈 문자열", () => {
    expect(synthesizeBubbleMessage("unknown_type")).toBe("");
  });
});

describe("BUBBLE_EVENT_TYPES", () => {
  it("4가지 이벤트 유형 포함", () => {
    expect(BUBBLE_EVENT_TYPES.has("agent_start")).toBe(true);
    expect(BUBBLE_EVENT_TYPES.has("agent_end")).toBe(true);
    expect(BUBBLE_EVENT_TYPES.has("agent_dispatch")).toBe(true);
    expect(BUBBLE_EVENT_TYPES.has("agent_message")).toBe(true);
  });

  it("task_start, task_end 미포함", () => {
    expect(BUBBLE_EVENT_TYPES.has("task_start")).toBe(false);
    expect(BUBBLE_EVENT_TYPES.has("task_end")).toBe(false);
  });
});
