import type { SignalView } from "../types";

interface SignalChipProps {
  label: SignalView | null;
  /** 접근성 라벨 보강용 — "단기" | "장기" 등 */
  kind: string;
}

interface ChipStyle {
  bg: string;
  fg: string;
  border: string;
  outline: boolean;
}

const CHIP_STYLES: Record<SignalView, ChipStyle> = {
  강력매수: { bg: "#15803d", fg: "#ffffff", border: "#15803d", outline: false },
  // 매수: 라임(#65a30d)은 흰 글자 대비 AA 미달 → 더 진한 올리브그린(#4d7c0f, ~5:1)
  매수: { bg: "#4d7c0f", fg: "#ffffff", border: "#4d7c0f", outline: false },
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

export function SignalChip({ label, kind }: SignalChipProps) {
  const { display, style } = resolveStyle(label);

  return (
    <span
      className={`signal-chip${style.outline ? " signal-chip--outline" : ""}`}
      style={{
        backgroundColor: style.bg,
        color: style.fg,
        borderColor: style.border,
      }}
      aria-label={`${kind} 관점: ${display}`}
    >
      {display}
    </span>
  );
}
