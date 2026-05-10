"use client";

import { useEffect } from "react";
import TaskScroll from "@/components/scroll/TaskScroll";
import ManagerCharacter from "@/components/characters/ManagerCharacter";
import ChatBubble from "@/components/chat/ChatBubble";
import KingInput from "@/components/input/KingInput";
import { useEventStore, selectLatestMessages } from "@/stores/eventStore";
import { CHARACTERS } from "@/lib/characters";
import { createEventStream } from "@/lib/eventStream";

/** 단청 오방색 — 화공 variant A 균등 5등분 */
const DANCHEONG_COLORS = [
  { name: "청", hex: "#2C5F8D" },
  { name: "적", hex: "#D94F2B" },
  { name: "황", hex: "#C9A84C" },
  { name: "백", hex: "#E8DCC8" },
  { name: "흑", hex: "#2D2926" },
] as const;

/** 매니저 4인 고정 목록 */
const MANAGER_NAMES = [
  "planner-dojeon",
  "implementer-yeongsil",
  "reviewer-sunsin",
  "ideator-yagyong",
] as const;

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
  const latestMessages = useEventStore((s) => selectLatestMessages(s, 5));

  const taskTitle = currentTask?.title ?? "대기 중";
  // currentTask 이벤트 수를 진행 단계로 임시 표시 (M2.x에서 step 구조화 예정)
  const taskStep =
    currentTask != null && currentTask.events.length > 0
      ? { current: currentTask.events.length, total: currentTask.events.length }
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

      {/* ── 매니저 무대 ── */}
      <section
        className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-8 items-center justify-items-center px-4 py-6"
        aria-label="매니저 회의실"
      >
        {MANAGER_NAMES.map((managerName) => (
          <ManagerCharacter
            key={managerName}
            agentName={managerName}
            isActive={activeManagers.has(managerName)}
            visibleDojes={Array.from(activeDojes).filter(
              (name) => CHARACTERS[name]?.parent === managerName
            )}
          />
        ))}
      </section>

      {/* ── 말풍선 로그 ── */}
      <section
        className="h-48 overflow-y-auto flex flex-col gap-3 px-4 py-3 border-t"
        style={{
          borderColor: "var(--bg-hanji-shadow)",
          backgroundColor: "var(--bg-hanji-dark)",
        }}
        aria-label="대화 로그"
        role="log"
        aria-live="polite"
      >
        {latestMessages.length > 0 ? (
          latestMessages.map((e) => (
            <ChatBubble
              key={e.id}
              agentName={e.agentName}
              message={e.message ?? ""}
            />
          ))
        ) : (
          <p
            className="text-sm text-center mt-8"
            style={{ color: "#9CA3AF", fontFamily: "var(--font-serif)" }}
          >
            임금의 명을 기다립니다…
          </p>
        )}
      </section>

      {/* ── 임금 입력창 ── */}
      <KingInput />
    </main>
  );
}
