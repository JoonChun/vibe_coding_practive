"use client";

import { useState } from "react";
import { useEventStore } from "@/stores/eventStore";

export default function KingInput() {
  const [value, setValue] = useState("");

  const handleSend = () => {
    const text = value.trim();
    if (!text) return;
    const taskId = `mock-${Date.now()}`;
    useEventStore.getState().addEvent({
      id: `mock-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: Date.now(),
      type: "task_start",
      agentName: "king",
      taskId,
      message: text,
    });
    setValue("");
  };

  return (
    <div
      className="h-14 flex items-center gap-3 px-4 border-t"
      style={{
        backgroundColor: "var(--bg-hanji-dark)",
        borderColor: "var(--bg-hanji-shadow)",
      }}
    >
      {/* 임금 emoji 라벨 */}
      <label
        htmlFor="king-input"
        className="text-xl shrink-0"
        aria-hidden="true"
      >
        🤴
      </label>

      {/* 입력창 */}
      <input
        id="king-input"
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            handleSend();
          }
        }}
        placeholder="임금의 명이 이르시면…"
        aria-label="임금 입력창"
        className="flex-1 h-9 px-3 rounded-lg border text-sm"
        style={{
          backgroundColor: "var(--bg-hanji)",
          borderColor: "var(--bg-hanji-shadow)",
          color: "var(--color-ink)",
          fontFamily: "var(--font-serif)",
        }}
      />
    </div>
  );
}
