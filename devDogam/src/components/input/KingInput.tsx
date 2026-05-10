export default function KingInput() {
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
        className="text-xl shrink-0 cursor-not-allowed"
        aria-hidden="true"
      >
        🤴
      </label>

      {/* 입력창 */}
      <input
        id="king-input"
        type="text"
        disabled
        placeholder="임금의 명이 이르시면…"
        aria-label="임금 입력창"
        aria-disabled="true"
        className="flex-1 h-9 px-3 rounded-lg border text-sm cursor-not-allowed"
        style={{
          backgroundColor: "var(--bg-hanji-shadow)",
          borderColor: "var(--bg-hanji-shadow)",
          color: "var(--color-ink-light)",
          fontFamily: "var(--font-serif)",
        }}
      />
    </div>
  );
}
