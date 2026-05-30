"use client";

import { useEffect, useMemo, useState } from "react";
import TaskScroll from "@/components/scroll/TaskScroll";
import ManagerCharacter from "@/components/characters/ManagerCharacter";
import DojeFloorRow from "@/components/characters/DojeFloorRow";
import KingCharacter from "@/components/characters/KingCharacter";
import IlwolObongdo from "@/components/background/IlwolObongdo";
import KingInput from "@/components/input/KingInput";
import { useEventStore } from "@/stores/eventStore";
import { CHARACTERS } from "@/lib/characters";
import { createEventStream } from "@/lib/eventStream";
import { deriveManagerBubbles } from "@/lib/managerBubbles";

/** 단청 오방색 — 화공 variant A 균등 5등분. 옵션 A 전환 후 DOM 사용 없음 — 이력 보존 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const DANCHEONG_COLORS = [
  { name: "청", hex: "#2C5F8D" },
  { name: "적", hex: "#D94F2B" },
  { name: "황", hex: "#C9A84C" },
  { name: "백", hex: "#E8DCC8" },
  { name: "흑", hex: "#2D2926" },
] as const;

/** 말풍선 폴백 — 이벤트 없을 때 말풍선 숨김 (idle 시 조용한 어전) */

/** 매니저 4인 어전 도열 좌표 — v3: 카펫 양옆 도열 (발 끝 기준 translate(-50%,-100%)) */
const MANAGER_LAYOUT = [
  { name: "planner-dojeon", side: "left" as const, style: { left: "38%", top: "65%" } },
  { name: "ideator-yagyong", side: "left" as const, style: { left: "18%", top: "75%" } },
  { name: "implementer-yeongsil", side: "right" as const, style: { left: "82%", top: "75%" } },
  { name: "reviewer-sunsin", side: "right" as const, style: { left: "62%", top: "65%" } },
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

  // agent_end 말풍선 10초 후 자동 사라짐(TTL) 트리거용 1초 ticker.
  // 서버 SSR 시 0 → fade 비활성 (hydration mismatch 방지).
  // 클라이언트 mount 후 setInterval로 Date.now() 갱신 → managerBubbles 재계산.
  const [now, setNow] = useState(0);
  useEffect(() => {
    setNow(Date.now());
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  /** 매니저별 가장 최근 말풍선 메시지 1개 (agent_end는 10초 후 자동 숨김) */
  const managerBubbles = useMemo(
    () => deriveManagerBubbles(events, now),
    [events, now]
  );

  /**
   * 매니저별 절 모션 trigger key.
   *
   * §7: 여러 매니저가 연속 보고 시 각자 절 — 1명 제한 폐기.
   * 최근 5개 이벤트 window 안의 agent_message·agent_end 를 모두 수집.
   * 각 매니저마다 가장 최근 trigger 이벤트의 id(또는 timestamp)를 bowEventKey 로 부여.
   * bowEventKey 값이 바뀔 때마다 절 1회 발동 (단청도제 M3.2-3에서 useEffect 연결 예정).
   *
   * 반환형: Record<string, string | undefined>  (managerName → bowEventKey)
   * (Date.now() impure 회피 — events 배열의 기존 id/ts 필드 사용)
   */
  const managerBowTriggers = useMemo(() => {
    const map: Record<string, string | undefined> = {};
    const window = events.slice(-5);
    for (const e of window) {
      if (e.type !== "agent_message" && e.type !== "agent_end") continue;
      if (!CHARACTERS[e.agentName]?.manager) continue;
      // 나중 이벤트가 앞 이벤트를 덮어씀 → 자연스럽게 가장 최근 trigger 보존
      map[e.agentName] = e.id;
    }
    return map;
  }, [events]);

  // task_start/task_end는 UserPromptSubmit/Stop 훅이 emit (Phase 2 E).
  // 훅이 빈 prompt나 미발동 상태일 때 대비해 합성 fallback 유지.
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
      {/* ── 상단 바 — 옵션 A: 단색 #4A2C2A (어전 천장 단청은 SVG 내부에만 표현) ── */}
      <header className="relative h-12 flex shrink-0" role="banner" style={{ backgroundColor: "#4A2C2A" }}>
        {/* 오방색 5등분 div 제거 — SVG 내부 천장 띠와 중복 방지 */}
        {/* DANCHEONG_COLORS 상수는 이력 보존을 위해 유지 */}

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

        {/* 임금 (z:20) — v2.2: top 45%, 옥좌 단상 윗면(SVG y≈240~280) 정합, translate(-50%,-100%) */}
        <div
          className="absolute"
          style={{ left: "50%", top: "45%", transform: "translate(-50%, -100%)", zIndex: 20 }}
        >
          <KingCharacter
            message={managerBubbles["king"]}
            isActive={isActive}
          />
        </div>

        {/* 품계석 — 매니저 발 아래 고정. z=2 (마루 위, 매니저 아래) */}
        {MANAGER_LAYOUT.map((m) => (
          <div
            key={`${m.name}-pumgyeseok`}
            className="absolute"
            style={{
              ...m.style,                                  // 매니저와 동일 left/top
              transform: "translate(-50%, 0)",             // 매니저는 -100% (발바닥) → 품계석은 0 (그 아래)
              width: "28px",
              height: "8px",
              backgroundColor: "#8B7355",
              border: "1px solid #1A1410",
              zIndex: 2,
              pointerEvents: "none",
            }}
            aria-hidden="true"
          />
        ))}

        {/* 도제 12인 마룻바닥 일렬 (z:5) */}
        <DojeFloorRow activeDojes={activeDojes} dojeBubbles={managerBubbles} />

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
              side={m.side}
              message={managerBubbles[m.name]}
              bowTrigger={managerBowTriggers[m.name]}
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
