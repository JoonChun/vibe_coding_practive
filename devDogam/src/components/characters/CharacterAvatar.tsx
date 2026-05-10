"use client";

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

  if (!character) {
    console.warn(
      `[CharacterAvatar] 알 수 없는 agentName: "${agentName}". CHARACTERS에 등록되지 않은 키요.`
    );
    return null;
  }

  const px = SIZE_MAP[size];

  const idx = getCharacterIndex(agentName);
  const delay = idx >= 0 ? (idx * 0.2) % 2 : 0; // 0~2초 사이 stagger

  return (
    <motion.div
      animate={prefersReducedMotion ? undefined : { y: [0, -2, 0] }}
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
