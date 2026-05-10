// ── AgentEvent 이벤트 스키마 (PHASE-1-SPEC.md §4.1) ──────────────────────────

export type AgentEventType =
  | "task_start"      // 임금 명령 시작
  | "task_end"        // 작업 종료
  | "agent_start"     // 에이전트 호출됨
  | "agent_message"   // 에이전트가 한 번 발화
  | "agent_end"       // 에이전트 응답 완료
  | "agent_dispatch"; // 매니저가 도제 위임

export interface AgentEvent {
  id: string;                        // ulid
  timestamp: number;                 // Unix ms
  type: AgentEventType;
  agentName: string;                 // "planner-dojeon" 등
  parentAgent?: string;              // 위임 시 매니저 이름
  taskId: string;                    // 한 작업 단위 묶음
  message?: string;                  // 짧은 발화 요약 (말풍선용)
  metadata?: Record<string, unknown>;
}

// ── 파생 헬퍼 타입 ────────────────────────────────────────────────────────────

/**
 * 한 task 단위 묶음. task_start 이벤트 수신 시 생성.
 * title 은 task_start 의 message 필드에서 가져온다.
 */
export interface TaskBundle {
  taskId: string;
  startedAt: number;
  events: AgentEvent[];
  endedAt?: number;
  title?: string;
}

/**
 * 현재 활성 상태인 에이전트 집합.
 * Zustand store 외부에서도 참조할 수 있도록 별도 타입으로 분리.
 */
export interface ActiveAgents {
  managers: Set<string>;
  dojes: Set<string>;
}
