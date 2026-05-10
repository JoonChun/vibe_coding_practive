import { CHARACTERS } from "@/lib/characters";

interface Props {
  agentName: string;
  message: string;
  side?: "left" | "right" | "center";
}

export default function ChatBubble({ agentName, message, side = "left" }: Props) {
  const character = CHARACTERS[agentName];
  if (!character) return null;

  const tailStyle =
    side === "right"
      ? {
          borderTop: "6px solid transparent",
          borderBottom: "6px solid transparent",
          borderLeft: `12px solid ${character.hex}`,
        }
      : side === "center"
      ? {
          borderLeft: "6px solid transparent",
          borderRight: "6px solid transparent",
          borderTop: `12px solid ${character.hex}`,
        }
      : {
          borderTop: "6px solid transparent",
          borderBottom: "6px solid transparent",
          borderRight: `12px solid ${character.hex}`,
        };

  const tailClassName =
    side === "right"
      ? "absolute -right-3 top-4 w-0 h-0"
      : side === "center"
      ? "absolute -bottom-3 left-1/2 -translate-x-1/2 w-0 h-0"
      : "absolute -left-3 top-4 w-0 h-0";

  return (
    <article
      className="relative rounded-2xl px-3 py-2 border-2"
      style={{
        borderColor: character.hex,
        backgroundColor: "var(--bg-hanji)",
        fontFamily: "var(--font-serif)",
      }}
      aria-label={`${character.displayName}: ${message}`}
    >
      {/* 말풍선 꼬리 */}
      <span
        className={tailClassName}
        style={tailStyle}
        aria-hidden="true"
      />

      {/* 메시지 — 발화자 식별은 말풍선 위치(캐릭터 머리 위)로 대신함 */}
      <span
        className={character.manager ? "text-xs font-semibold" : "text-xs font-normal"}
        style={{
          color: "var(--color-ink)",
          display: "block",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          maxWidth: "140px",
          textAlign: "center",
        }}
      >
        {message}
      </span>
    </article>
  );
}
