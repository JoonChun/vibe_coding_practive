import type { DecisionView } from "../types";

interface DistributionStripProps {
  counts: Record<DecisionView, number>;
  total: number;
}

const SEGMENTS: { key: DecisionView; label: string; color: string }[] = [
  { key: "강력매수", label: "강력매수", color: "#15803d" },
  { key: "매수", label: "매수", color: "#65a30d" },
  { key: "관망", label: "관망", color: "#6b7280" },
  { key: "매도", label: "매도", color: "#dc2626" },
  { key: "강력매도", label: "강력매도", color: "#7f1d1d" },
];

/** 단기관점 5단계 분포를 색 세그먼트 가로 막대 + 라벨·카운트로 표시 (데이터부족 제외) */
export function DistributionStrip({ counts, total }: DistributionStripProps) {
  const barLabel = SEGMENTS.map((seg) => `${seg.label} ${counts[seg.key]}개`).join(
    ", "
  );

  return (
    <section className="distribution" aria-label="단기 판정 분포 요약">
      <div className="distribution__header">
        <h3 className="distribution__title">단기 판정 분포</h3>
        <span className="distribution__meta">
          {total > 0 ? `총 ${total}개 종목` : "집계할 데이터 없음"}
        </span>
      </div>
      <div className="distribution__bar" role="img" aria-label={barLabel}>
        {total === 0 ? (
          <div className="distribution__bar-empty" />
        ) : (
          SEGMENTS.map((seg) => {
            const pct = (counts[seg.key] / total) * 100;
            if (pct <= 0) return null;
            return (
              <div
                key={seg.key}
                className="distribution__segment"
                style={{ width: `${pct}%`, backgroundColor: seg.color }}
                title={`${seg.label}: ${counts[seg.key]}`}
              />
            );
          })
        )}
      </div>
      <div className="distribution__labels">
        {SEGMENTS.map((seg) => (
          <div key={seg.key} className="distribution__label">
            <span
              className="distribution__label-text"
              style={{ color: seg.color }}
            >
              {seg.label}
            </span>
            <span className="distribution__label-count">{counts[seg.key]}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
