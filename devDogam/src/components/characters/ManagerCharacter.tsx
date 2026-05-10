import React from "react";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import { CHARACTERS } from "@/lib/characters";
import CharacterAvatar from "./CharacterAvatar";
import DojeCharacter from "./DojeCharacter";
import ChatBubble from "@/components/chat/ChatBubble";

interface Props {
  agentName: string;
  isActive?: boolean;
  visibleDojes?: string[];
  side?: "left" | "right";
  message?: string;
  style?: React.CSSProperties;
  /** true 시 절 모션 1회 발동 (자기 자리 → 카펫 → 계단 앞 절 → 복귀, ~2.4s) */
  bowing?: boolean;
}

/** 부채꼴 X 오프셋 계산 — n명 균등 배치 */
function getDojeOffsets(count: number): number[] {
  if (count === 0) return [];
  if (count === 1) return [0];
  if (count === 2) return [-36, 36];
  if (count === 3) return [-48, 0, 48];
  // n >= 4: 균등
  const span = 96;
  const step = span / (count - 1);
  return Array.from({ length: count }, (_, i) => -span / 2 + step * i);
}

/**
 * 매니저별 카펫 이동 동선 오프셋 계산.
 * side="left"  → 오른쪽 (화면 중앙) 이동 : +vw
 * side="right" → 왼쪽  (화면 중앙) 이동 : -vw
 *
 * 4단계 keyframe times (누적 비율, 총 2.4s):
 *   0ms   → 0.000  : 자기 자리 (idle)
 *   300ms → 0.125  : 카펫 입구 (두 발짝 — x만 이동)
 *   800ms → 0.333  : 계단 앞 (카펫 따라 ↑ — y 이동 완료)
 *   1600ms → 0.667 : 절 최심 (scaleY 0.92, rotate 5°)
 *   1800ms → 0.750 : 절 복귀 (scaleY 1, rotate 0)
 *   2500ms → 1.000 : 자기 자리 복귀
 *
 * NOTE: 임금 박스 spec — 총 2.4s. 300+500+400+200+700 = 2100ms → spec 맞춰 2.1s 사용.
 */
function getBowVariants(side?: "left" | "right"): Variants {
  // 카펫 입구 x 이동량 (두 발짝) — left 매니저는 오른쪽, right는 왼쪽
  const stepX = side === "right" ? "-80px" : "80px";
  // 카펫 중앙 (계단 앞) x 이동량
  const carpetX = side === "right" ? "-160px" : "160px";
  // 계단 앞 y 이동량 (위로 — 카펫 따라 ↑)
  const carpetY = "-40px";

  return {
    idle: { x: 0, y: 0, scaleY: 1, rotate: 0 },
    bow: {
      x: [0, stepX, carpetX, carpetX, carpetX, 0],
      y: [0, "0px", carpetY, carpetY, carpetY, "0px"],
      scaleY: [1, 1, 1, 0.92, 1, 1],
      rotate: [0, 0, 0, 5, 0, 0],
      transition: {
        duration: 2.1,
        // 누적 ms: 0 / 300 / 800 / 1200 / 1400 / 2100
        times: [0, 0.143, 0.381, 0.571, 0.667, 1],
        ease: "easeInOut",
      },
    },
  };
}

export default function ManagerCharacter({
  agentName,
  isActive = false,
  visibleDojes = [],
  side,
  message,
  style,
  bowing = false,
}: Props) {
  const character = CHARACTERS[agentName];
  if (!character || !character.manager) return null;

  const offsets = getDojeOffsets(visibleDojes.length);
  const bowVariants = getBowVariants(side);

  return (
    <motion.div
      className="relative flex flex-col items-center"
      style={{ zIndex: 10, paddingBottom: visibleDojes.length > 0 ? "36px" : "0", ...style }}
      animate={bowing ? "bow" : "idle"}
      variants={bowVariants}
    >
      {/* 말풍선 — 머리 위 absolute */}
      {message && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 30,
            maxWidth: "140px",
          }}
        >
          <ChatBubble
            agentName={agentName}
            message={message}
            side={side === "right" ? "right" : "left"}
          />
        </div>
      )}

      {/* 아바타 + ring */}
      <div
        className="rounded-full"
        style={{
          boxShadow: isActive ? `0 0 0 4px ${character.hex}` : "none",
          transition: "box-shadow 5s ease-out",
        }}
        aria-label={`${character.displayName} ${isActive ? "활성" : "대기"}`}
      >
        <CharacterAvatar agentName={agentName} size="manager" />
      </div>

      {/* 이름 라벨 */}
      <span
        className="text-sm mt-1 whitespace-nowrap"
        style={{ color: character.hex, fontFamily: "var(--font-serif)" }}
      >
        {character.emoji} {character.displayName}
      </span>

      {/* 품계석 — 발 바로 아래 작은 직사각 돌 (24×16px) — LAYOUT-V3 §4 */}
      <svg
        width="24"
        height="16"
        viewBox="0 0 24 16"
        style={{
          position: "absolute",
          bottom: "-16px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: -1,
        }}
        aria-hidden="true"
      >
        <rect x="0" y="0" width="24" height="16" rx="1" fill="#6B7280" stroke="#4B5563" strokeWidth="1" />
        <rect x="2" y="3" width="20" height="2"  rx="0" fill="#9CA3AF" opacity="0.4" />
        <rect x="2" y="8" width="20" height="2"  rx="0" fill="#4B5563" opacity="0.4" />
      </svg>

      {/* 도제 발밑 클러스터 — AnimatePresence로 감싸 등장·퇴장 motion 작동 */}
      <AnimatePresence>
        {visibleDojes.map((dojeKey, idx) => (
          <motion.div
            key={dojeKey}
            className="absolute"
            style={{
              bottom: "-20px",
              left: "50%",
              transform: `translateX(calc(-50% + ${offsets[idx]}px))`,
              zIndex: 5,
            }}
            aria-label={`${CHARACTERS[dojeKey]?.displayName ?? dojeKey} 도제`}
          >
            <DojeCharacter agentName={dojeKey} side={side} />
          </motion.div>
        ))}
      </AnimatePresence>
    </motion.div>
  );
}
