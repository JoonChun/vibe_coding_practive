import { motion } from "framer-motion";
import { CHARACTERS } from "@/lib/characters";
import CharacterAvatar from "./CharacterAvatar";

interface Props {
  agentName: string;
  isActive?: boolean;
  side?: "left" | "right";
}

export default function DojeCharacter({
  agentName,
  isActive = false,
  side,
}: Props) {
  const character = CHARACTERS[agentName];
  if (!character || character.manager) return null;

  const xInitial = side === "right" ? 60 : -60;

  return (
    <motion.div
      initial={{ x: xInitial, y: 30, opacity: 0 }}
      animate={{ x: 0, y: 0, opacity: 1, transition: { duration: 0.5, ease: "easeOut" } }}
      exit={{ x: xInitial, y: 30, opacity: 0, transition: { duration: 0.3, ease: "easeIn" } }}
      className="flex flex-col items-center gap-1"
    >
      {/* 아바타 + ring */}
      <div
        className="rounded-full"
        style={{
          boxShadow: isActive ? `0 0 0 2px ${character.hex}` : "none",
        }}
        aria-label={`${character.displayName} ${isActive ? "활성" : "대기"}`}
      >
        <CharacterAvatar agentName={agentName} size="doje" />
      </div>

      {/* 이름 라벨 */}
      <span
        className="text-xs whitespace-nowrap"
        style={{ color: character.hex, fontFamily: "var(--font-serif)" }}
      >
        {character.displayName}
      </span>
    </motion.div>
  );
}
