// ── managerBowTriggers 회귀 시험 (M3.2-2) ────────────────────────────────────
// page.tsx의 managerBowTriggers useMemo 로직을 순수 함수로 검증.
// 동일 로직: events.slice(-5) window 안 agent_message/agent_end 매니저 이벤트만,
// 각 매니저당 가장 나중 event.id를 보존 (덮어쓰기).

import { describe, it, expect } from "vitest";
import { CHARACTERS } from "@/lib/characters";
import type { AgentEvent } from "@/types/events";

// ── 순수 함수 — page.tsx useMemo 로직과 동일 ─────────────────────────────────
function deriveManagerBowTriggers(
  events: AgentEvent[]
): Record<string, string | undefined> {
  const map: Record<string, string | undefined> = {};
  const window = events.slice(-5);
  for (const e of window) {
    if (e.type !== "agent_message" && e.type !== "agent_end") continue;
    if (!CHARACTERS[e.agentName]?.manager) continue;
    map[e.agentName] = e.id;
  }
  return map;
}

// ── 헬퍼 ─────────────────────────────────────────────────────────────────────
let seq = 0;
function makeEvent(
  type: AgentEvent["type"],
  agentName: string,
  id?: string
): AgentEvent {
  seq++;
  return {
    id: id ?? `e-${seq}`,
    timestamp: seq,
    type,
    agentName,
    taskId: "t-bow",
  };
}

// ── 테스트 ────────────────────────────────────────────────────────────────────

describe("deriveManagerBowTriggers — 기본 동작", () => {
  it("빈 배열이면 빈 객체 반환", () => {
    expect(deriveManagerBowTriggers([])).toEqual({});
  });

  it("agent_message 매니저 이벤트 → 해당 매니저 id 반환", () => {
    const events = [makeEvent("agent_message", "planner-dojeon", "msg-1")];
    const result = deriveManagerBowTriggers(events);
    expect(result["planner-dojeon"]).toBe("msg-1");
  });

  it("agent_end 매니저 이벤트 → 해당 매니저 id 반환", () => {
    const events = [makeEvent("agent_end", "reviewer-sunsin", "end-1")];
    const result = deriveManagerBowTriggers(events);
    expect(result["reviewer-sunsin"]).toBe("end-1");
  });

  it("도제 이벤트(agent_message)는 무시됨 — manager:false인 agentName", () => {
    // planning-hojo는 도제(manager: false)
    const events = [makeEvent("agent_message", "planning-hojo", "doje-1")];
    const result = deriveManagerBowTriggers(events);
    expect(result["planning-hojo"]).toBeUndefined();
    expect(Object.keys(result)).toHaveLength(0);
  });

  it("agent_start / agent_dispatch 이벤트는 무시됨", () => {
    const events = [
      makeEvent("agent_start",    "planner-dojeon", "start-1"),
      makeEvent("agent_dispatch", "planner-dojeon", "dispatch-1"),
    ];
    const result = deriveManagerBowTriggers(events);
    expect(result["planner-dojeon"]).toBeUndefined();
  });
});

describe("deriveManagerBowTriggers — 다중 매니저 & 최신 id 보존", () => {
  it("매니저 4인 각 1개 이벤트 — 4인 모두 키 존재", () => {
    const events = [
      makeEvent("agent_message", "planner-dojeon",       "p-1"),
      makeEvent("agent_end",     "implementer-yeongsil", "i-1"),
      makeEvent("agent_message", "reviewer-sunsin",      "r-1"),
      makeEvent("agent_end",     "ideator-yagyong",      "y-1"),
    ];
    const result = deriveManagerBowTriggers(events);
    expect(result["planner-dojeon"]).toBe("p-1");
    expect(result["implementer-yeongsil"]).toBe("i-1");
    expect(result["reviewer-sunsin"]).toBe("r-1");
    expect(result["ideator-yagyong"]).toBe("y-1");
  });

  it("같은 매니저 이벤트 2개 — 나중 이벤트(배열 뒤쪽) id 보존", () => {
    const events = [
      makeEvent("agent_message", "planner-dojeon", "old-id"),
      makeEvent("agent_end",     "planner-dojeon", "new-id"),
    ];
    const result = deriveManagerBowTriggers(events);
    // for 루프 덮어쓰기 → 나중 이벤트(new-id)가 보존됨
    expect(result["planner-dojeon"]).toBe("new-id");
  });
});

describe("deriveManagerBowTriggers — slice(-5) window 동작 (M3.2-2 핵심)", () => {
  it("정확히 5개 이벤트 — 5개 모두 window 내 포함", () => {
    // 매니저 5가지 이벤트 (실제 매니저는 4인이므로 일부 중복)
    const events = [
      makeEvent("agent_message", "planner-dojeon",       "w-1"),
      makeEvent("agent_end",     "implementer-yeongsil", "w-2"),
      makeEvent("agent_message", "reviewer-sunsin",      "w-3"),
      makeEvent("agent_end",     "ideator-yagyong",      "w-4"),
      makeEvent("agent_message", "planner-dojeon",       "w-5"),
    ];
    const result = deriveManagerBowTriggers(events);
    // planner-dojeon: w-5(나중 이벤트)
    expect(result["planner-dojeon"]).toBe("w-5");
    expect(result["implementer-yeongsil"]).toBe("w-2");
    expect(result["reviewer-sunsin"]).toBe("w-3");
    expect(result["ideator-yagyong"]).toBe("w-4");
  });

  it("6번째 이벤트 추가 시 첫 이벤트는 window 밖으로 밀려남", () => {
    // 이벤트 6개: 첫 번째(implementer-yeongsil) → slice(-5) 후 제외되어야 함
    const events = [
      makeEvent("agent_message", "implementer-yeongsil", "out-of-window"),  // 6번째 후 제외
      makeEvent("agent_message", "planner-dojeon",       "w-2"),
      makeEvent("agent_end",     "reviewer-sunsin",      "w-3"),
      makeEvent("agent_message", "ideator-yagyong",      "w-4"),
      makeEvent("agent_end",     "planner-dojeon",       "w-5"),
      makeEvent("agent_message", "reviewer-sunsin",      "w-6"),  // 6번째
    ];
    const result = deriveManagerBowTriggers(events);
    // implementer-yeongsil은 window 밖 → 없어야 함
    expect(result["implementer-yeongsil"]).toBeUndefined();
    // 나머지는 window 내 최신 id
    expect(result["planner-dojeon"]).toBe("w-5");
    expect(result["reviewer-sunsin"]).toBe("w-6");
    expect(result["ideator-yagyong"]).toBe("w-4");
  });

  it("window 내 이벤트가 도제+매니저 혼재 시 매니저만 추출", () => {
    const events = [
      makeEvent("agent_message", "planning-hojo",        "doje-1"),  // 도제
      makeEvent("agent_message", "frontend-dancheong",   "doje-2"),  // 도제
      makeEvent("agent_message", "planner-dojeon",       "mgr-1"),   // 매니저
      makeEvent("agent_end",     "backend-gigwan",       "doje-3"),  // 도제
      makeEvent("agent_end",     "implementer-yeongsil", "mgr-2"),   // 매니저
    ];
    const result = deriveManagerBowTriggers(events);
    expect(result["planner-dojeon"]).toBe("mgr-1");
    expect(result["implementer-yeongsil"]).toBe("mgr-2");
    // 도제는 없어야 함
    expect(result["planning-hojo"]).toBeUndefined();
    expect(result["frontend-dancheong"]).toBeUndefined();
    expect(result["backend-gigwan"]).toBeUndefined();
    expect(Object.keys(result)).toHaveLength(2);
  });

  it("5개보다 적은 이벤트 배열 — slice(-5)는 전체 반환 (안전)", () => {
    const events = [
      makeEvent("agent_message", "planner-dojeon", "only-1"),
      makeEvent("agent_end",     "reviewer-sunsin", "only-2"),
    ];
    const result = deriveManagerBowTriggers(events);
    expect(result["planner-dojeon"]).toBe("only-1");
    expect(result["reviewer-sunsin"]).toBe("only-2");
  });

  it("window 내 이벤트가 전부 agent_start/dispatch이면 빈 객체", () => {
    const events = [
      makeEvent("agent_start",    "planner-dojeon",       "s-1"),
      makeEvent("agent_dispatch", "implementer-yeongsil", "s-2"),
      makeEvent("agent_start",    "reviewer-sunsin",      "s-3"),
    ];
    const result = deriveManagerBowTriggers(events);
    expect(Object.keys(result)).toHaveLength(0);
  });
});
