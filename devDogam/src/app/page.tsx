"use client";

import { useEffect, useMemo } from "react";
import TaskScroll from "@/components/scroll/TaskScroll";
import ManagerCharacter from "@/components/characters/ManagerCharacter";
import KingCharacter from "@/components/characters/KingCharacter";
import IlwolObongdo from "@/components/background/IlwolObongdo";
import KingInput from "@/components/input/KingInput";
import { useEventStore } from "@/stores/eventStore";
import { CHARACTERS } from "@/lib/characters";
import { createEventStream } from "@/lib/eventStream";
import { deriveManagerBubbles } from "@/lib/managerBubbles";

/** 단청 오방색 — 화공 variant A 균등 5등분 */
const DANCHEONG_COLORS = [
  { name: "청", hex: "#2C5F8D" },
  { name: "적", hex: "#D94F2B" },
  { name: "황", hex: "#C9A84C" },
  { name: "백", hex: "#E8DCC8" },
  { name: "흑", hex: "#2D2926" },
] as const;

/** 말풍선 폴백 — 이벤트 없을 때 말풍선 숨김 (idle 시 조용한 어전) */

/** 매니저 4인 어전 도열 좌표 — 임금 분부 V5: 가장자리·하단 분산 */
const MANAGER_LAYOUT = [
  { name: "planner-dojeon",       side: "left"  as const, style: { left: "12%", top: "55%" } },
  { name: "ideator-yagyong",      side: "left"  as const, style: { left: "8%",  top: "78%" } },
  { name: "implementer-yeongsil", side: "right" as const, style: { left: "88%", top: "78%" } },
  { name: "reviewer-sunsin",      side: "right" as const, style: { left: "92%", top: "55%" } },
] as const;

// BUBBLE_EVENT_TYPES, synthesizeBubbleMessage → @/lib/managerBubbles 로 분리됨

export default function Page() {
  // ── M2.2 SSE 연결 (eventStream 클라이언트 래퍼) ───────────────────────────
  useEffect(() => {
    const addEvent = useEventStore.getState().addEvent;
    const setConnected = useEventStore.getState().setConnected;
    const cleanup = createEventStream(addEvent, setConnected);
    return cleanup;
  }, []);

  // ── store 구독 ─────────────────────────────────────────────────────────────
  const activeManagers = useEventStore((s) => s.activeManagers);
  const activeDojes = useEventStore((s) => s.activeDojes);
  const currentTask = useEventStore((s) => s.currentTask);
  const isConnected = useEventStore((s) => s.isConnected);
  // 결함 수정: selector를 store에서 직접 쓰면 매 호출마다 새 배열을 반환해
  // useSyncExternalStore가 무한 루프 의심함.
  // → events 배열만 구독하고 useMemo로 derived 계산.
  // 또한 훅이 agent_message를 emit하지 않으므로 라이프사이클 이벤트도
  // 합성 메시지로 말풍선화 (Phase 2 transcript 파싱 전까지 임시).
  const events = useEventStore((s) => s.events);

  /** 매니저별 가장 최근 말풍선 메시지 1개 */
  const managerBubbles = useMemo(() => deriveManagerBubbles(events), [events]);

  /**
   * 매니저별 절 모션 trigger.
   * 단순화: events 배열 최후미에서 agent_message·agent_end 이벤트를 가진
   * 매니저를 최대 1명 찾아 bowing=true 로 표시.
   * events 변화마다 재계산되므로 새 이벤트 수신 시마다 절 1회 발동.
   * (Date.now() impure 회피 — 순수 함수 useMemo)
   */
  const managerBowing = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i];
      if (e.type !== "agent_message" && e.type !== "agent_end") continue;
      if (!CHARACTERS[e.agentName]?.manager) continue;
      // 가장 최근 매니저 보고 이벤트 1개만 절 발동
      map[e.agentName] = true;
      break;
    }
    return map;
  }, [events]);

  // 훅이 task_start를 emit하지 않으므로 currentTask?.title 은 항상 null.
  // → activeManagers/activeDojes 상태로 합성 제목 도출.
  // (진짜 user prompt 텍스트는 Phase 2의 UserPromptSubmit 훅으로 대체 예정)
  const isActive = activeManagers.size > 0 || activeDojes.size > 0;
  const taskTitle =
    currentTask?.title ??
    (isActive ? "사건 진행 중…" : "대기 중");
  // currentTask 이벤트 수를 진행 단계로 임시 표시 (M2.x에서 step 구조화 예정)
  // currentTask 없을 때는 활성 에이전트 수로 대체
  const activeCount = activeManagers.size + activeDojes.size;
  const taskStep =
    currentTask != null && currentTask.events.length > 0
      ? { current: currentTask.events.length, total: currentTask.events.length }
      : isActive
        ? { current: activeCount, total: activeCount }
        : undefined;

  return (
    <main
      className="flex flex-col h-screen overflow-hidden"
      style={{ backgroundColor: "var(--bg-hanji)" }}
    >
      {/* ── 단청 오방색 상단 바 ── */}
      <header className="relative h-12 flex shrink-0" role="banner">
        {/* 오방색 5등분 */}
        {DANCHEONG_COLORS.map((c) => (
          <div
            key={c.name}
            className="flex-1"
            style={{ backgroundColor: c.hex }}
            aria-hidden="true"
          />
        ))}

        {/* 한자 타이틀 — absolute 오버레이 */}
        <div className="absolute inset-0 flex items-center justify-between px-4 pointer-events-none">
          <h1
            className="text-base font-bold leading-none drop-shadow"
            style={{
              color: "#FFFFFF",
              fontFamily: "var(--font-serif)",
              textShadow: "0 1px 4px rgba(0,0,0,0.7)",
            }}
          >
            개발도감(開發都監)
          </h1>

          {/* 연결 상태 표시 */}
          <span
            className="text-xs flex items-center gap-1"
            style={{
              color: "#E0E0E0",
              textShadow: "0 1px 3px rgba(0,0,0,0.8)",
            }}
            aria-label={isConnected ? "연결 상태: 실시간" : "연결 상태: 끊김"}
          >
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{
                backgroundColor: isConnected ? "#22C55E" : "#9CA3AF",
              }}
              aria-hidden="true"
            />
            {isConnected ? "실시간" : "끊김"}
          </span>
        </div>
      </header>

      {/* ── 두루마리 (TaskScroll) ── */}
      <TaskScroll
        title={taskTitle}
        step={taskStep}
      />

      {/* ── 어전 도열 ── */}
      <section
        className="flex-1 relative overflow-hidden"
        aria-label="어전 도열 — 임금과 매니저 4인"
      >
        {/* 일월오봉도 배경 (z:0) */}
        <IlwolObongdo />

        {/* 임금 (z:20) — LAYOUT-V4 §4: top 40%, 단상 위 정합, translate(-50%,-100%) */}
        <div
          className="absolute"
          style={{ left: "50%", top: "40%", transform: "translate(-50%, -100%)", zIndex: 20 }}
        >
          <KingCharacter
            message={managerBubbles["king"]}
            isActive={isActive}
          />
        </div>

        {/* 매니저 4인 (z:10) */}
        {MANAGER_LAYOUT.map((m) => (
          <div
            key={m.name}
            className="absolute"
            style={{ ...m.style, transform: "translate(-50%, -100%)", zIndex: 10 }}
          >
            <ManagerCharacter
              agentName={m.name}
              isActive={activeManagers.has(m.name)}
              visibleDojes={Array.from(activeDojes).filter(
                (d) => CHARACTERS[d]?.parent === m.name
              )}
              side={m.side}
              message={managerBubbles[m.name]}
              bowing={managerBowing[m.name] ?? false}
            />
          </div>
        ))}

        {/* 숨김 aria-live — 스크린리더 말풍선 전달 */}
        <div className="sr-only" aria-live="polite">
          {Object.entries(managerBubbles).map(([name, msg]) => (
            <div key={name}>
              {CHARACTERS[name]?.displayName ?? name}: {msg}
            </div>
          ))}
        </div>
      </section>

      {/* ── 임금 입력창 ── */}
      <KingInput />
    </main>
  );
}
