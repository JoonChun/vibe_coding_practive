"use client";

import React from "react";
import CharacterAvatar from "./CharacterAvatar";
import ChatBubble from "@/components/chat/ChatBubble";

interface Props {
  message?: string;
  isActive?: boolean;
  style?: React.CSSProperties;
}

export default function KingCharacter({
  message,
  isActive = false,
  style,
}: Props) {
  return (
    <div
      style={{ position: "relative", ...style }}
      aria-label={`임금 ${isActive ? "작업 중" : "대기 중"}`}
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
            maxWidth: "160px",
          }}
        >
          <ChatBubble agentName="king" message={message} side="center" />
        </div>
      )}

      {/* 아바타 + active ring */}
      <div style={{ position: "relative", display: "inline-block" }}>
        <div
          className="rounded-full"
          style={
            isActive
              ? {
                  boxShadow:
                    "0 0 0 2px #C0392B, 0 0 0 4px var(--bg-hanji), 0 0 0 6px #C0392B",
                }
              : {
                  boxShadow: "none",
                }
          }
        >
          <CharacterAvatar agentName="king" size="king" />
        </div>

        {/* 옥좌 단상은 IlwolObongdo.tsx 에서 처리됨 — LAYOUT-V4 §3.1 */}
      </div>

      {/* 이름 라벨 */}
      <span
        className="block text-center text-sm mt-4 whitespace-nowrap"
        style={{
          color: "#F4ECD8",
          fontFamily: "var(--font-serif)",
        }}
      >
        🤴 임금
      </span>
    </div>
  );
}
