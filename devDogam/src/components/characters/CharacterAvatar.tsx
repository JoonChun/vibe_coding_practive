"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { CHARACTERS, getCharacterIndex } from "@/lib/characters";

interface Props {
  agentName: string;
  size?: "manager" | "doje" | "king";
  className?: string;
}

const SIZE_MAP = {
  manager: 64,
  doje: 40,
  king: 80,
} as const;

export default function CharacterAvatar({
  agentName,
  size = "manager",
  className,
}: Props) {
  const character = CHARACTERS[agentName];
  const prefersReducedMotion = useReducedMotion();
  // SSR hydration 결함 방지:
  // useReducedMotion()이 서버(null)와 클라이언트(boolean) 결과 달라
  // hydration mismatch 일으킴. mounted 플래그로 클라이언트 마운트 후에만 애니 적용.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 의도적 마운트 표지 (SSR hydration mismatch 회피용)
    setMounted(true);
  }, []);

  if (!character) {
    console.warn(
      `[CharacterAvatar] 알 수 없는 agentName: "${agentName}". CHARACTERS에 등록되지 않은 키요.`
    );
    return null;
  }

  const px = SIZE_MAP[size];

  const idx = getCharacterIndex(agentName);
  const delay = idx >= 0 ? (idx * 0.2) % 2 : 0; // 0~2초 sttagger

  // 마운트 전 (SSR / 첫 렌더): 애니 X. 서버·클라이언트 동일한 정적 결과 보장.
  // 마운트 후 + reduced motion 비활성: idle 흔들기 적용.
  const shouldAnimate = mounted && !prefersReducedMotion;

  return (
    <motion.div
      animate={shouldAnimate ? { y: [0, -2, 0] } : undefined}
      transition={{
        duration: 2,
        repeat: Infinity,
        ease: "easeInOut",
        delay,
      }}
      style={{ display: "inline-block" }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/characters/${agentName}.svg`}
        alt={character.displayName}
        width={px}
        height={px}
        className={className}
        draggable={false}
      />
    </motion.div>
  );
}
