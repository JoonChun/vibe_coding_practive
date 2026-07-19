import type { SignalView } from "../types";

interface SignalChipProps {
  label: SignalView | null;
  /** 접근성 라벨 보강용 — "단기" | "장기" 등 */
  kind: string;
  /** "live"면 실시간 참고 판정용 저채도 외곽선 스타일(.signal-chip--live) — 확정 판정(confirmed)을 압도하지 않게 */
  variant?: "confirmed" | "live";
}

interface ChipStyle {
  bg: string;
  fg: string;
  border: string;
  outline: boolean;
}

const CHIP_STYLES: Record<SignalView, ChipStyle> = {
  강력매수: { bg: "#15803d", fg: "#ffffff", border: "#15803d", outline: false },
  매수: { bg: "#65a30d", fg: "#ffffff", border: "#65a30d", outline: false },
  관망: { bg: "#6b7280", fg: "#ffffff", border: "#6b7280", outline: false },
  매도: { bg: "#dc2626", fg: "#ffffff", border: "#dc2626", outline: false },
  강력매도: { bg: "#7f1d1d", fg: "#ffffff", border: "#7f1d1d", outline: false },
  데이터부족: {
    bg: "transparent",
    fg: "#6b7280",
    border: "#9ca3af",
    outline: true,
  },
};

// 값이 null 이거나 알 수 없는 문자열이 와도 안전하게 "데이터부족" 취급
function resolveStyle(label: SignalView | null): {
  display: string;
  style: ChipStyle;
} {
  if (label && label in CHIP_STYLES) {
    return { display: label, style: CHIP_STYLES[label] };
  }
  return { display: "데이터부족", style: CHIP_STYLES["데이터부족"] };
}

export function SignalChip({ label, kind, variant = "confirmed" }: SignalChipProps) {
  const { display, style } = resolveStyle(label);
  const isLive = variant === "live";

  return (
    <span
      className={`signal-chip${style.outline ? " signal-chip--outline" : ""}${
        isLive ? " signal-chip--live" : ""
      }`}
      style={{
        backgroundColor: isLive ? "transparent" : style.bg,
        color: isLive ? style.border : style.fg,
        borderColor: style.border,
      }}
      aria-label={`${kind} 관점: ${display}`}
    >
      {display}
    </span>
  );
}
