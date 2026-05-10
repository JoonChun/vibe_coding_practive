import { CHARACTERS } from "@/lib/characters";
import CharacterAvatar from "./CharacterAvatar";
import DojeCharacter from "./DojeCharacter";

interface Props {
  agentName: string;
  isActive?: boolean;
  visibleDojes?: string[];
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

export default function ManagerCharacter({
  agentName,
  isActive = false,
  visibleDojes = [],
}: Props) {
  const character = CHARACTERS[agentName];
  if (!character || !character.manager) return null;

  const offsets = getDojeOffsets(visibleDojes.length);

  return (
    <div
      className="relative flex flex-col items-center"
      style={{ zIndex: 10, paddingBottom: visibleDojes.length > 0 ? "36px" : "0" }}
    >
      {/* 아바타 + ring */}
      <div
        className="rounded-full"
        style={
          isActive
            ? { boxShadow: `0 0 0 4px ${character.hex}` }
            : { boxShadow: "0 0 0 1px #9ca3af" }
        }
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

      {/* 도제 발밑 클러스터 */}
      {visibleDojes.map((dojeKey, idx) => (
        <div
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
          <DojeCharacter agentName={dojeKey} />
        </div>
      ))}
    </div>
  );
}
