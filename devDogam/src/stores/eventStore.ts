// ── eventStore.ts — Zustand 이벤트 저장소 (PHASE-1-SPEC.md §4, M2.1) ─────────

import { create } from "zustand";
import { CHARACTERS } from "@/lib/characters";
import type { AgentEvent, TaskBundle } from "@/types/events";

// ── 상태 타입 ────────────────────────────────────────────────────────────────

interface EventStoreState {
  /** append-only 이벤트 목록, 최대 200개 유지 */
  events: AgentEvent[];
  /** 현재 agent_start ~ agent_end 사이에 있는 매니저 집합 */
  activeManagers: Set<string>;
  /** 현재 agent_start ~ agent_end 사이에 있는 도제 집합 */
  activeDojes: Set<string>;
  /** 현재 진행 중인 task. task_end 이후에도 참조 가능하도록 유지 */
  currentTask: TaskBundle | null;
  /** M2.2 SSE 연결 상태. M2.1 기본값 false */
  isConnected: boolean;
}

// ── 액션 타입 ────────────────────────────────────────────────────────────────

interface EventStoreActions {
  /**
   * 새 이벤트 추가. type별 부수 상태(activeManagers, currentTask 등)도 갱신.
   * events 배열이 200개 초과 시 앞 50개 drop.
   */
  addEvent(event: AgentEvent): void;
  /** 전체 초기화 */
  resetAll(): void;
  /** M2.2용 연결 상태 setter */
  setConnected(connected: boolean): void;
}

// ── 상수 ─────────────────────────────────────────────────────────────────────

const MAX_EVENTS = 200;
const DROP_COUNT = 50;

// ── store ─────────────────────────────────────────────────────────────────────

export const useEventStore = create<EventStoreState & EventStoreActions>(
  (set, get) => ({
    // 초기 상태
    events: [],
    activeManagers: new Set<string>(),
    activeDojes: new Set<string>(),
    currentTask: null,
    isConnected: false,

    // ── addEvent ──────────────────────────────────────────────────────────────
    addEvent(event: AgentEvent) {
      const state = get();

      // 1) events 배열 업데이트 (최대 200개)
      let nextEvents = [...state.events, event];
      if (nextEvents.length > MAX_EVENTS) {
        nextEvents = nextEvents.slice(DROP_COUNT);
      }

      // 2) currentTask 업데이트용 변수
      let nextTask = state.currentTask;

      // 3) activeManagers / activeDojes 업데이트용 변수
      let nextManagers = state.activeManagers;
      let nextDojes = state.activeDojes;

      // 4) type별 처리
      switch (event.type) {
        case "task_start": {
          nextTask = {
            taskId: event.taskId,
            startedAt: event.timestamp,
            events: [event],
            title: event.message,
          };
          break;
        }

        case "task_end": {
          if (nextTask) {
            nextTask = {
              ...nextTask,
              endedAt: event.timestamp,
              events: [...nextTask.events, event],
            };
          }
          break;
        }

        case "agent_start": {
          const meta = CHARACTERS[event.agentName];
          if (meta) {
            if (meta.manager) {
              nextManagers = new Set([...nextManagers, event.agentName]);
            } else {
              nextDojes = new Set([...nextDojes, event.agentName]);
              // 도제가 속한 매니저도 활성으로 표시
              if (meta.parent) {
                nextManagers = new Set([...nextManagers, meta.parent]);
              }
            }
          }
          // currentTask에도 이벤트 추가
          if (nextTask) {
            nextTask = {
              ...nextTask,
              events: [...nextTask.events, event],
            };
          }
          break;
        }

        case "agent_end": {
          const meta = CHARACTERS[event.agentName];
          if (meta) {
            if (meta.manager) {
              nextManagers = new Set([...nextManagers].filter(n => n !== event.agentName));
            } else {
              nextDojes = new Set([...nextDojes].filter(n => n !== event.agentName));
            }
          }
          if (nextTask) {
            nextTask = {
              ...nextTask,
              events: [...nextTask.events, event],
            };
          }
          break;
        }

        case "agent_dispatch": {
          // parentAgent가 있으면 매니저로 활성화
          if (event.parentAgent) {
            nextManagers = new Set([...nextManagers, event.parentAgent]);
          }
          // 위임 대상(agentName)이 도제라면 activeDojes에도 추가
          const meta = CHARACTERS[event.agentName];
          if (meta && !meta.manager) {
            nextDojes = new Set([...nextDojes, event.agentName]);
          }
          if (nextTask) {
            nextTask = {
              ...nextTask,
              events: [...nextTask.events, event],
            };
          }
          break;
        }

        case "agent_message": {
          // events에만 들어감. currentTask에도 단순 push
          if (nextTask) {
            nextTask = {
              ...nextTask,
              events: [...nextTask.events, event],
            };
          }
          break;
        }
      }

      set({
        events: nextEvents,
        activeManagers: nextManagers,
        activeDojes: nextDojes,
        currentTask: nextTask,
      });
    },

    // ── resetAll ──────────────────────────────────────────────────────────────
    resetAll() {
      set({
        events: [],
        activeManagers: new Set<string>(),
        activeDojes: new Set<string>(),
        currentTask: null,
        isConnected: false,
      });
    },

    // ── setConnected ──────────────────────────────────────────────────────────
    setConnected(connected: boolean) {
      set({ isConnected: connected });
    },
  })
);

// ── Selector 함수 (store 외부 export) ─────────────────────────────────────────

/**
 * agent_message 이벤트 중 최신 n개를 반환.
 *
 * @example
 *   const msgs = useEventStore(s => selectLatestMessages(s, 5));
 */
export const selectLatestMessages = (
  state: EventStoreState & EventStoreActions,
  n = 5
): AgentEvent[] =>
  state.events.filter((e) => e.type === "agent_message").slice(-n);

/**
 * 특정 매니저 소속 도제 중 현재 활성(activeDojes) 인 목록 반환.
 *
 * @example
 *   const dojes = useEventStore(s => selectActiveDojesByManager(s, "planner-dojeon"));
 */
export const selectActiveDojesByManager = (
  state: EventStoreState & EventStoreActions,
  managerName: string
): string[] =>
  Array.from(state.activeDojes).filter(
    (name) => CHARACTERS[name]?.parent === managerName
  );
