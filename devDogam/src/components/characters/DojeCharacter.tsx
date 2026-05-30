"use client";

import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CHARACTERS } from "@/lib/characters";
import { DOJE_CARPET_START_Y } from "@/lib/carpetPath";
import { getCharacterIndex } from "@/lib/characters";
import CharacterAvatar from "./CharacterAvatar";
import ChatBubble from "@/components/chat/ChatBubble";

interface Props {
  agentName: string;
  isActive?: boolean;
  side?: "left" | "right";
  /** 도제 말풍선 메시지 */
  message?: string;
}

export default function DojeCharacter({
  agentName,
  isActive = false,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  side,
  message,
}: Props) {
  // Hook은 항상 최상단 — early return 이전에 호출
  // mount 이후 활성 bobbing 적용 — SSR mismatch 방지
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  const character = CHARACTERS[agentName];
  if (!character || character.manager) return null;

  // index 기반 deterministic delay (SSR-safe)
  const dojeIndex = getCharacterIndex(agentName);
  const bobbingDelay = dojeIndex * 0.15;

  // D3 + D6 통합 animate:
  // - mount 전: initial(y=DOJE_CARPET_START_Y) → animate(y=0) 1회 진입
  // - mount 후 + isActive: y=[-6,-8,-6] 반복 + scale=1.08 (bobbing + 부상)
  // - mount 후 + 비활성: y=0, scale=1
  const animateProps = mounted
    ? isActive
      ? {
          y: [-6, -8, -6] as number[],
          scale: 1.08,
          opacity: 1,
        }
      : {
          y: 0,
          scale: 1,
          opacity: 1,
        }
    : {
        y: 0,
        scale: 1,
        opacity: 1,
      };

  const transitionProps = mounted && isActive
    ? {
        y: {
          duration: 1.8,
          repeat: Infinity,
          ease: "easeInOut" as const,
          delay: bobbingDelay,
        },
        scale: { duration: 0.35, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] },
        opacity: { duration: 0.2 },
      }
    : mounted
      ? {
          y: { duration: 0.35, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] },
          scale: { duration: 0.35, ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number] },
          opacity: { duration: 0.2 },
        }
      : {
          opacity: { duration: 0.2, ease: "easeOut" as const },
          y: { duration: 0.5, ease: "easeOut" as const },
        };

  // D5 라벨 현판 — 활성 시 character.hex 배경 + 흰 글씨, 비활성 시 흐린 한지색
  const labelStyle = isActive
    ? {
        color: "#FFFFFF",
        backgroundColor: character.hex,
        padding: "1px 4px",
        borderRadius: "2px",
        minWidth: "48px",
        display: "inline-block",
        textAlign: "center" as const,
      }
    : {
        color: "#F4ECD8",
        minWidth: "48px",
        display: "inline-block",
        textAlign: "center" as const,
      };

  return (
    <motion.div
      // 최초 mount 1회 진입 연출: 카펫 하단에서 페이드인·슬라이드업
      initial={{ x: 0, y: DOJE_CARPET_START_Y, opacity: 0 }}
      animate={animateProps}
      transition={transitionProps}
      className="relative flex flex-col items-center gap-1"
    >
      {/* 말풍선 — 머리 위 absolute */}
      <AnimatePresence>
        {message && (
          <motion.div
            key={message}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1, transition: { duration: 0.15 } }}
            exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.15 } }}
            style={{
              position: "absolute",
              bottom: "calc(100% + 8px)",
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 30,
              maxWidth: "120px",
            }}
          >
            <ChatBubble
              agentName={agentName}
              message={message}
              side="center"
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* 아바타 + ring */}
      <div
        className="rounded-full"
        style={{
          boxShadow: isActive ? `0 0 0 2px ${character.hex}` : "none",
          // D3 부상 transition (비활성 복귀 시)
          transition: "box-shadow 0.35s ease-out",
        }}
        aria-label={`${character.displayName} ${isActive ? "활성" : "대기"}`}
      >
        <CharacterAvatar agentName={agentName} size="doje" />
      </div>

      {/* D5 이름 라벨 현판 */}
      <span
        className="text-xs whitespace-nowrap"
        style={{
          fontFamily: "var(--font-serif)",
          transition: "background-color 0.35s ease-out, color 0.35s ease-out",
          ...labelStyle,
        }}
      >
        {character.displayName}
      </span>
    </motion.div>
  );
}
