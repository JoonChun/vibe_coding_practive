import TaskScroll from "@/components/scroll/TaskScroll";
import ManagerCharacter from "@/components/characters/ManagerCharacter";
import ChatBubble from "@/components/chat/ChatBubble";
import KingInput from "@/components/input/KingInput";

/** 단청 오방색 — 화공 variant A 균등 5등분 */
const DANCHEONG_COLORS = [
  { name: "청", hex: "#2C5F8D" },
  { name: "적", hex: "#D94F2B" },
  { name: "황", hex: "#C9A84C" },
  { name: "백", hex: "#E8DCC8" },
  { name: "흑", hex: "#2D2926" },
] as const;

export default function Page() {
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
          <span
            className="text-xs flex items-center gap-1"
            style={{
              color: "#E0E0E0",
              textShadow: "0 1px 3px rgba(0,0,0,0.8)",
            }}
            aria-label="연결 상태: 정적"
          >
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: "#9CA3AF" }}
              aria-hidden="true"
            />
            정적
          </span>
        </div>
      </header>

      {/* ── 두루마리 (TaskScroll) ── */}
      <TaskScroll
        title="개발도감 Phase 1 시연"
        step={{ current: 3, total: 6 }}
      />

      {/* ── 매니저 무대 ── */}
      <section
        className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-8 items-center justify-items-center px-4 py-6"
        aria-label="매니저 회의실"
      >
        <ManagerCharacter
          agentName="planner-dojeon"
          isActive
          visibleDojes={["planning-hojo"]}
        />
        <ManagerCharacter agentName="implementer-yeongsil" />
        <ManagerCharacter agentName="reviewer-sunsin" />
        <ManagerCharacter agentName="ideator-yagyong" />
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
        <ChatBubble
          agentName="planner-dojeon"
          message="단계별 설계 올립니다."
        />
        <ChatBubble
          agentName="planning-hojo"
          message="P0 셋을 우선 처리하겠소이다."
        />
        <ChatBubble
          agentName="reviewer-sunsin"
          message="검수 통과 가능합니다."
        />
      </section>

      {/* ── 임금 입력창 ── */}
      <KingInput />
    </main>
  );
}
