"use client";

import { useState, useEffect, useRef } from "react";
import { sendKingPrompt } from "./kingInputLogic";

export default function KingInput() {
  const [value, setValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // 성공 직후 페이드 효과용 상태 (150ms transient)
  const [fadeSuccess, setFadeSuccess] = useState(false);

  // 에러 자동 해제 타이머
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // errorMsg 변경 시 5초 후 자동 해제
  useEffect(() => {
    if (errorMsg === null) return;

    // 이전 타이머 취소
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    errorTimerRef.current = setTimeout(() => {
      setErrorMsg(null);
    }, 5000);

    return () => {
      if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    };
  }, [errorMsg]);

  const isMock =
    process.env.NEXT_PUBLIC_KING_INPUT_MODE === "mock";

  const handleSend = async () => {
    // 더블 Enter 방어
    if (isLoading) return;

    const text = value.trim();
    if (!text) return;

    // mock 모드: 입력창만 비우고 종료
    if (isMock) {
      setValue("");
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    const result = await sendKingPrompt(text);

    if (result.ok) {
      setValue("");
      // 성공 페이드: 150ms transient 클래스
      setFadeSuccess(true);
      setTimeout(() => setFadeSuccess(false), 150);
    } else {
      setErrorMsg(result.message);
    }

    setIsLoading(false);
  };

  const placeholder = isMock
    ? "임금의 명이 이르시면… (mock)"
    : "임금의 명이 이르시면…";

  return (
    <div
      className="relative h-14 flex items-center gap-3 px-4 border-t"
      style={{
        backgroundColor: "var(--bg-hanji-dark)",
        borderColor: "var(--bg-hanji-shadow)",
      }}
    >
      {/* 에러 토스트 — 입력창 상단 절대위치 */}
      {errorMsg !== null && (
        <div
          role="alert"
          aria-live="assertive"
          style={{
            position: "absolute",
            bottom: "100%",
            left: "0",
            right: "0",
            margin: "0 0 4px 0",
            padding: "8px 36px 8px 12px",
            backgroundColor: "var(--bg-hanji)",
            color: "#D94F2B",
            border: "1px solid var(--bg-hanji-shadow)",
            borderRadius: "6px",
            fontSize: "0.8125rem",
            fontFamily: "var(--font-serif)",
            lineHeight: "1.4",
            zIndex: 50,
          }}
        >
          {errorMsg}
          {/* X 버튼 dismiss */}
          <button
            type="button"
            onClick={() => setErrorMsg(null)}
            aria-label="오류 메시지 닫기"
            style={{
              position: "absolute",
              top: "50%",
              right: "8px",
              transform: "translateY(-50%)",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "#D94F2B",
              fontSize: "1rem",
              lineHeight: 1,
              padding: "2px 4px",
            }}
          >
            ×
          </button>
        </div>
      )}

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
            void handleSend();
          }
        }}
        disabled={isLoading}
        placeholder={placeholder}
        aria-label="임금 입력창"
        aria-busy={isLoading}
        className="flex-1 h-9 px-3 rounded-lg border text-sm"
        style={{
          backgroundColor: "var(--bg-hanji)",
          borderColor: "var(--bg-hanji-shadow)",
          color: "var(--color-ink)",
          fontFamily: "var(--font-serif)",
          // 로딩 중 시각 피드백
          opacity: isLoading ? 0.5 : fadeSuccess ? 0.6 : 1,
          cursor: isLoading ? "wait" : "text",
          // 성공 페이드 transition
          transition: "opacity 150ms ease",
        }}
      />
    </div>
  );
}
