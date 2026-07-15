import type { BarItem } from "../types";

interface PriceChartProps {
  items: BarItem[];
  loading: boolean;
}

const WIDTH = 600;
const HEIGHT = 220;
const PADDING_X = 8;
const PADDING_Y = 12;

const UP_COLOR = "#dc2626"; // 양봉 적색 (국내 HTS 관행)
const DOWN_COLOR = "#2563eb"; // 음봉 청색

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

type CompleteBar = BarItem & {
  open: number;
  high: number;
  low: number;
  close: number;
};

function isCompleteBar(bar: BarItem): bar is CompleteBar {
  return (
    isFiniteNumber(bar.open) &&
    isFiniteNumber(bar.high) &&
    isFiniteNumber(bar.low) &&
    isFiniteNumber(bar.close)
  );
}

/** 일봉 캔들스틱 차트 (SVG 직접 렌더링). 데이터가 2개 미만이면 "축적 중" 안내로 대체. */
export function PriceChart({ items, loading }: PriceChartProps) {
  if (loading) {
    return (
      <div className="price-chart price-chart--empty">
        <p>차트를 불러오는 중…</p>
      </div>
    );
  }

  // 백엔드 응답에 결측(open/high/low/close 중 하나라도 null)인 봉이 섞여 있어도
  // 안전하게 걸러내고 렌더링한다.
  const bars = items.filter(isCompleteBar);

  if (bars.length < 2) {
    return (
      <div className="price-chart price-chart--empty">
        <p>차트 데이터 축적 중</p>
      </div>
    );
  }

  const highs = bars.map((b) => b.high);
  const lows = bars.map((b) => b.low);
  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const priceRange = maxPrice - minPrice || 1;

  const innerWidth = WIDTH - PADDING_X * 2;
  const innerHeight = HEIGHT - PADDING_Y * 2;
  const slot = innerWidth / bars.length;
  // 봉 개수가 적어도 캔들이 비대해지지 않도록 상한 클램프 (viewBox 단위)
  const candleWidth = Math.min(14, Math.max(2, slot * 0.6));

  function yFor(price: number): number {
    return PADDING_Y + innerHeight * (1 - (price - minPrice) / priceRange);
  }

  return (
    <div className="price-chart">
      <svg
        className="price-chart__svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`일봉 캔들스틱 차트, 최근 ${bars.length}일`}
      >
        {bars.map((bar, i) => {
          const x = PADDING_X + slot * i + slot / 2;
          const isUp = bar.close >= bar.open;
          const color = isUp ? UP_COLOR : DOWN_COLOR;
          const bodyTop = yFor(Math.max(bar.open, bar.close));
          const bodyBottom = yFor(Math.min(bar.open, bar.close));
          const bodyHeight = Math.max(1, bodyBottom - bodyTop);
          return (
            <g key={bar.date}>
              <line
                x1={x}
                x2={x}
                y1={yFor(bar.high)}
                y2={yFor(bar.low)}
                stroke={color}
                strokeWidth="1"
              />
              <rect
                x={x - candleWidth / 2}
                y={bodyTop}
                width={candleWidth}
                height={bodyHeight}
                fill={color}
              />
            </g>
          );
        })}
      </svg>
      <div className="price-chart__legend">
        <span className="price-chart__dot" aria-hidden="true" />
        <span>일봉 · 최근 {bars.length}일</span>
      </div>
    </div>
  );
}
