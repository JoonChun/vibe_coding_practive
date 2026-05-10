interface Props {
  title?: string;
  step?: { current: number; total: number };
}

export default function TaskScroll({
  title = "임금의 명을 기다립니다…",
  step,
}: Props) {
  const filledCount = step ? Math.round((step.current / step.total) * 10) : 0;
  const emptyCount = 10 - filledCount;

  return (
    <div
      className="h-16 flex items-center justify-between px-4 border-b"
      style={{
        backgroundColor: "var(--bg-hanji)",
        borderColor: "var(--bg-hanji-shadow)",
        fontFamily: "var(--font-serif)",
      }}
      role="status"
      aria-label={`현재 사건: ${title}${step ? `, 단계 ${step.current}/${step.total}` : ""}`}
    >
      {/* 좌측: 사건명 */}
      <span
        className="text-sm font-semibold truncate max-w-[60%]"
        style={{ color: "var(--color-ink)" }}
      >
        📜 사건: {title}
      </span>

      {/* 우측: 진행도 */}
      {step && (
        <div className="flex items-center gap-2 shrink-0">
          <div
            className="flex gap-[2px] text-xs leading-none"
            aria-hidden="true"
          >
            {Array.from({ length: filledCount }).map((_, i) => (
              <span
                key={`filled-${i}`}
                className="inline-block w-3 h-3 rounded-sm"
                style={{ backgroundColor: "var(--color-vermilion)" }}
              />
            ))}
            {Array.from({ length: emptyCount }).map((_, i) => (
              <span
                key={`empty-${i}`}
                className="inline-block w-3 h-3 rounded-sm"
                style={{ backgroundColor: "var(--bg-hanji-shadow)" }}
              />
            ))}
          </div>
          <span
            className="text-xs whitespace-nowrap"
            style={{ color: "var(--color-ink-light)" }}
          >
            단계 {step.current}/{step.total} 진행 중
          </span>
        </div>
      )}
    </div>
  );
}
