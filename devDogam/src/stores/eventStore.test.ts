// ── eventStore 단위 시험 ───────────────────────────────────────────────────────
// task_start → agent_start (매니저) → agent_start (도제) → agent_end → agent_message 흐름 검증

import { describe, it, expect, beforeEach } from "vitest";
import { useEventStore, selectLatestMessages, selectActiveDojesByManager } from "./eventStore";

// Zustand store 는 모듈 싱글턴이므로 각 테스트 전 초기화
beforeEach(() => {
  useEventStore.getState().resetAll();
});

// ── 헬퍼: 최소 AgentEvent 생성 ────────────────────────────────────────────────
let seq = 0;
function makeEvent(
  type: Parameters<ReturnType<typeof useEventStore.getState>["addEvent"]>[0]["type"],
  agentName: string,
  extra: Partial<Parameters<ReturnType<typeof useEventStore.getState>["addEvent"]>[0]> = {}
) {
  seq++;
  return {
    id: `evt-${seq}`,
    timestamp: Date.now() + seq,
    type,
    agentName,
    taskId: "t-001",
    ...extra,
  } as const;
}

describe("eventStore — 기본 흐름", () => {
  it("task_start: currentTask 생성, title 설정", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king", { message: "BMI 계산기 추가하라" }));

    const { currentTask } = useEventStore.getState();
    expect(currentTask).not.toBeNull();
    expect(currentTask?.title).toBe("BMI 계산기 추가하라");
    expect(currentTask?.taskId).toBe("t-001");
    expect(currentTask?.events).toHaveLength(1);
  });

  it("agent_start (매니저): activeManagers에 추가됨", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king"));
    addEvent(makeEvent("agent_start", "planner-dojeon"));

    const { activeManagers, activeDojes } = useEventStore.getState();
    expect(activeManagers.has("planner-dojeon")).toBe(true);
    expect(activeDojes.size).toBe(0);
  });

  it("agent_start (도제): activeDojes에 추가, 소속 매니저도 activeManagers에 추가", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king"));
    addEvent(makeEvent("agent_start", "planning-hojo")); // parent: planner-dojeon

    const { activeManagers, activeDojes } = useEventStore.getState();
    expect(activeDojes.has("planning-hojo")).toBe(true);
    expect(activeManagers.has("planner-dojeon")).toBe(true); // 부모 매니저도 활성
  });

  it("agent_end (매니저): activeManagers에서 제거됨", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king"));
    addEvent(makeEvent("agent_start", "planner-dojeon"));
    addEvent(makeEvent("agent_end", "planner-dojeon"));

    const { activeManagers } = useEventStore.getState();
    expect(activeManagers.has("planner-dojeon")).toBe(false);
  });

  it("agent_end (도제): activeDojes에서 제거됨", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king"));
    addEvent(makeEvent("agent_start", "planning-hojo"));
    addEvent(makeEvent("agent_end", "planning-hojo"));

    const { activeDojes } = useEventStore.getState();
    expect(activeDojes.has("planning-hojo")).toBe(false);
  });

  it("agent_message: events에 쌓이고, currentTask.events에도 추가됨", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king"));
    addEvent(makeEvent("agent_message", "planner-dojeon", { message: "설계 완료" }));

    const state = useEventStore.getState();
    expect(state.events.filter((e) => e.type === "agent_message")).toHaveLength(1);
    expect(state.currentTask?.events.some((e) => e.type === "agent_message")).toBe(true);
  });

  it("task_end: currentTask.endedAt 설정됨", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king"));
    const endTs = Date.now() + 9999;
    addEvent({ ...makeEvent("task_end", "king"), timestamp: endTs });

    const { currentTask } = useEventStore.getState();
    expect(currentTask?.endedAt).toBe(endTs);
  });
});

describe("eventStore — events 200개 초과 시 앞 50개 drop", () => {
  it("201번째 이벤트 추가 시 총 개수 151개", () => {
    const { addEvent } = useEventStore.getState();

    for (let i = 0; i < 201; i++) {
      addEvent({
        id: `bulk-${i}`,
        timestamp: i,
        type: "agent_message",
        agentName: "planner-dojeon",
        taskId: "t-bulk",
        message: `메시지 ${i}`,
      });
    }

    const { events } = useEventStore.getState();
    expect(events.length).toBe(151); // 201 - 50 = 151
  });
});

describe("selectLatestMessages selector", () => {
  it("최신 5개 agent_message만 반환", () => {
    const { addEvent } = useEventStore.getState();

    for (let i = 0; i < 8; i++) {
      addEvent({
        id: `msg-${i}`,
        timestamp: i,
        type: "agent_message",
        agentName: "planner-dojeon",
        taskId: "t-sel",
        message: `메시지 ${i}`,
      });
    }

    const msgs = selectLatestMessages(useEventStore.getState(), 5);
    expect(msgs).toHaveLength(5);
    expect(msgs[4].message).toBe("메시지 7"); // 마지막 5개의 끝
  });
});

describe("selectActiveDojesByManager selector", () => {
  it("planner-dojeon 소속 도제만 반환", () => {
    const { addEvent } = useEventStore.getState();

    addEvent(makeEvent("task_start", "king"));
    addEvent(makeEvent("agent_start", "planning-hojo"));   // parent: planner-dojeon
    addEvent(makeEvent("agent_start", "backend-gigwan"));  // parent: implementer-yeongsil

    const state = useEventStore.getState();
    const dojes = selectActiveDojesByManager(state, "planner-dojeon");
    expect(dojes).toContain("planning-hojo");
    expect(dojes).not.toContain("backend-gigwan");
  });
});
