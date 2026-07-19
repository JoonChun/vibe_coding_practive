import type { PullbackStatus } from "../types";

interface PullbackBadgeProps {
  status: PullbackStatus | null;
  reason: string | null;
}

/** 눌림 국면일 때만 존재감을 갖는 상태 3종 — 그 외(추세아님/추세지속/데이터부족/null)는 비표시(정보 소음 최소화). */
const VISIBLE_STATUSES: ReadonlySet<PullbackStatus> = new Set([
  "눌림 진행중(관망)",
  "눌림목 반등(매수후보)",
  "눌림 이탈(무효)",
]);

// 새 색을 만들지 않고 기존 팔레트를 재사용 — 매수/관망은 SignalChip.CHIP_STYLES와 동일 색,
// 이탈(무효)은 FactorBreakdown의 톤다운 적색(factor-row__fill--neg)을 재사용해 확정 판정보다 채도를 낮춘다.
const STATUS_COLOR: Record<"눌림 진행중(관망)" | "눌림목 반등(매수후보)" | "눌림 이탈(무효)", string> = {
  "눌림목 반등(매수후보)": "#65a30d",
  "눌림 진행중(관망)": "#6b7280",
  "눌림 이탈(무효)": "#f87171",
};

/** 눌림목 판정 배지 — StockDetailPage 장기 탭 전용, 게이지 카드 아래·FactorBreakdown 위 배치.
 * 눌림 국면(진행중/반등/이탈) 3상태일 때만 외곽선 칩 + 보조 설명으로 조용히 노출한다. */
export function PullbackBadge({ status, reason }: PullbackBadgeProps) {
  if (status === null || !VISIBLE_STATUSES.has(status)) return null;

  const color = STATUS_COLOR[status as keyof typeof STATUS_COLOR];

  return (
    <div className="pullback-badge">
      <span className="pullback-badge__chip" style={{ color, borderColor: color }}>
        {status}
      </span>
      {reason ? <p className="pullback-badge__reason">{reason}</p> : null}
    </div>
  );
}
