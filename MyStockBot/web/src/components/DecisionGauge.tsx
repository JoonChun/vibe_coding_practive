import type { ReactNode } from "react";
import type { SignalView } from "../types";

interface DecisionGaugeProps {
  view: SignalView | null;
  /** 프론트에서 재계산한 기여점수 합(합계 우선 표기 규칙 — utils/factorScoring 참조) */
  score: number | null;
  /** 임계값 — 단기 2, 장기 3 */
  threshold: number;
  /** "방금" / "3초 전" 등 상대 시간 문자열 */
  relativeTime: string;
  /** 게이지 카드 안, 확정 판정 body 아래에 추가로 렌더할 콘텐츠 — LiveReferenceStrip(full) 삽입용.
   * 게이지 SVG·바늘·확정 라벨은 이 prop과 무관하게 100% 기존 그대로 유지된다. */
  liveStrip?: ReactNode;
}

// 5단계 시맨틱 컬러 (SignalChip.tsx·DistributionStrip.tsx와 동일 값 유지)
const SEGMENT_COLORS = ["#7f1d1d", "#dc2626", "#6b7280", "#65a30d", "#15803d"];
const INSUFFICIENT_SEGMENT_COLOR = "#d1d5db"; // gray-300
const VIEW_COLORS: Record<string, string> = {
  강력매도: "#7f1d1d",
  매도: "#dc2626",
  관망: "#6b7280",
  매수: "#65a30d",
  강력매수: "#15803d",
};

const CENTER_X = 50;
const CENTER_Y = 50;
const ARC_RADIUS = 40;
const NEEDLE_RADIUS = 34;

function polarPoint(radius: number, angleDeg: number): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return {
    x: CENTER_X + radius * Math.cos(rad),
    y: CENTER_Y - radius * Math.sin(rad),
  };
}

function arcPath(startAngle: number, endAngle: number): string {
  const start = polarPoint(ARC_RADIUS, startAngle);
  const end = polarPoint(ARC_RADIUS, endAngle);
  // sweep=1: 화면 좌표(y아래)에서 왼쪽→오른쪽 상단 반원을 위로 볼록하게 그림
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${ARC_RADIUS} ${ARC_RADIUS} 0 0 1 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
}

// 반원 5구간: 왼쪽(180˚, 강력매도) → 오른쪽(0˚, 강력매수), 각 36˚
const SEGMENTS = [0, 1, 2, 3, 4].map((i) => ({
  start: 180 - i * 36,
  end: 180 - (i + 1) * 36,
}));

/**
 * AI 종합 분석 반원 게이지. 바늘 각도는 score를 [-threshold, +threshold]로 클램프한 뒤
 * 180˚(강력매도) ~ 0˚(강력매수) 범위로 선형 매핑한다.
 */
export function DecisionGauge({
  view,
  score,
  threshold,
  relativeTime,
  liveStrip,
}: DecisionGaugeProps) {
  const insufficient = view === null || view === "데이터부족" || score === null;

  const clampedScore = insufficient ? 0 : Math.max(-threshold, Math.min(threshold, score));
  const needleAngle = insufficient
    ? 90
    : 180 - ((clampedScore + threshold) / (2 * threshold)) * 180;
  const needleTip = polarPoint(NEEDLE_RADIUS, needleAngle);
  const needleColor = insufficient ? "#9ca3af" : "#1e293b";
  const labelColor = insufficient ? "#6b7280" : (VIEW_COLORS[view as string] ?? "#6b7280");

  const ariaLabel = insufficient
    ? "AI 종합 분석: 판정 보류, 데이터 부족"
    : `AI 종합 분석: ${view}, 스코어 ${score! > 0 ? "+" : ""}${score}, 임계 플러스마이너스 ${threshold}`;

  return (
    <div className="gauge-card">
      <h3 className="gauge-card__title">AI 종합 분석</h3>
      <div className="gauge-card__svg-wrap">
        <svg
          className="gauge-card__svg"
          viewBox="0 0 100 50"
          role="img"
          aria-label={ariaLabel}
        >
          {SEGMENTS.map((seg, i) => (
            <path
              key={seg.start}
              d={arcPath(seg.start, seg.end)}
              fill="none"
              stroke={insufficient ? INSUFFICIENT_SEGMENT_COLOR : SEGMENT_COLORS[i]}
              strokeWidth="8"
              strokeLinecap="round"
            />
          ))}
          <line
            className="gauge-card__needle"
            x1={CENTER_X}
            y1={CENTER_Y}
            x2={needleTip.x}
            y2={needleTip.y}
            stroke={needleColor}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <circle cx={CENTER_X} cy={CENTER_Y} r="3" fill={needleColor} />
        </svg>
      </div>
      {insufficient ? (
        <div className="gauge-card__body">
          <div className="gauge-card__label" style={{ color: labelColor }}>
            판정 보류
          </div>
          <p className="gauge-card__caption">데이터 부족</p>
        </div>
      ) : (
        <div className="gauge-card__body">
          <div className="gauge-card__label" style={{ color: labelColor }}>
            {view}
          </div>
          <p className="gauge-card__caption">
            판정 갱신 · {relativeTime}
            <br />
            스코어 {score! > 0 ? "+" : ""}
            {score} (임계 ±{threshold})
          </p>
        </div>
      )}
      {liveStrip}
    </div>
  );
}
