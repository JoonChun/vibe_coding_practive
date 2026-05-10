import { CHARACTERS } from "@/lib/characters";
import CharacterAvatar from "./CharacterAvatar";

interface Props {
  agentName: string;
  isActive?: boolean;
}

export default function DojeCharacter({ agentName, isActive = false }: Props) {
  const character = CHARACTERS[agentName];
  if (!character || character.manager) return null;

  return (
    <div className="flex flex-col items-center gap-1">
      {/* 아바타 + ring */}
      <div
        className="rounded-full"
        style={
          isActive
            ? { boxShadow: `0 0 0 2px ${character.hex}` }
            : { boxShadow: "0 0 0 1px #9ca3af" }
        }
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
    </div>
  );
}
