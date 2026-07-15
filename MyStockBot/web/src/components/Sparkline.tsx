import { useSparkline } from "../hooks/useSparkline";

interface SparklineProps {
  code: string;
  /** 상승 추세면 초록, 하락이면 빨강, 그 외 회색 */
  trendUp: boolean;
  trendDown: boolean;
}

const UP_COLOR = "#dc2626"; // 상승 적색 (국내 HTS 관행)
const DOWN_COLOR = "#2563eb"; // 하락 청색
const FLAT_COLOR = "#94a3b8"; // slate-400

/**
 * 최근 종가로 그리는 미니 추이선. 데이터가 부족(2개 미만)하거나
 * 조회에 실패하면 아무것도 렌더링하지 않는다(카드 레이아웃은 유지).
 */
export function Sparkline({ code, trendUp, trendDown }: SparklineProps) {
  const closes = useSparkline(code, 20);

  if (!closes || closes.length < 2) {
    return null;
  }

  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const stepX = 100 / (closes.length - 1);
  const points = closes
    .map((value, index) => {
      const x = index * stepX;
      const y = 18 - ((value - min) / range) * 16;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const stroke = trendUp ? UP_COLOR : trendDown ? DOWN_COLOR : FLAT_COLOR;

  return (
    <svg
      className="stock-card__sparkline"
      viewBox="0 0 100 20"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
