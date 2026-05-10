import { CHARACTERS } from "@/lib/characters";

interface Props {
  agentName: string;
  message: string;
}

export default function ChatBubble({ agentName, message }: Props) {
  const character = CHARACTERS[agentName];
  if (!character) return null;

  const isManager = character.manager;

  return (
    <article
      className="relative rounded-2xl px-4 py-3 border-2"
      style={{
        borderColor: character.hex,
        backgroundColor: "var(--bg-hanji)",
        fontFamily: "var(--font-serif)",
      }}
      aria-label={`${character.displayName}: ${message}`}
    >
      {/* 말풍선 꼬리 — 좌측 소삼각형 */}
      <span
        className="absolute -left-3 top-4 w-0 h-0"
        style={{
          borderTop: "6px solid transparent",
          borderBottom: "6px solid transparent",
          borderRight: `12px solid ${character.hex}`,
        }}
        aria-hidden="true"
      />

      {/* 발화자 + 메시지 */}
      <div
        className={`flex items-start gap-2 ${isManager ? "text-base font-semibold" : "text-sm font-normal"}`}
        style={{ color: "var(--color-ink)" }}
      >
        <span
          className="shrink-0"
          style={{ color: character.hex }}
          aria-hidden="true"
        >
          {character.emoji} {character.displayName}:
        </span>
        <span>{message}</span>
      </div>
    </article>
  );
}
