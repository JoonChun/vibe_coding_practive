import type { SnapshotSource } from "../types";

interface SourceBadgeProps {
  source: SnapshotSource | null;
}

const SOURCE_LABEL: Record<SnapshotSource, string> = {
  kis: "KIS 실시간",
  yfinance: "Yahoo 지연",
};

export function SourceBadge({ source }: SourceBadgeProps) {
  if (source === "kis") {
    return (
      <span className="source-badge source-badge--kis">
        {SOURCE_LABEL.kis}
      </span>
    );
  }
  if (source === "yfinance") {
    return (
      <span className="source-badge source-badge--yfinance">
        {SOURCE_LABEL.yfinance}
      </span>
    );
  }
  return <span className="source-badge source-badge--unknown">알 수 없음</span>;
}
