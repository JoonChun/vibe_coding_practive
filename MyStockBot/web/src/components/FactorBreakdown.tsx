import { type FactorRow, sumFactorScores } from "../utils/factorScoring";

interface FactorBreakdownProps {
  rows: FactorRow[] | null;
  /** 판정 임계값(단기 2·장기 3) — 합계와 함께 "왜 이 판정인지" 캡션에 사용 */
  threshold?: number;
}

function scoreColor(score: number): string {
  if (score > 0) return "#16a34a";
  if (score < 0) return "#dc2626";
  return "#6b7280";
}

/** 기여요인 분해 — 중앙 0선 기준 좌(음수·빨강)/우(양수·초록) Tug-of-War 바 */
export function FactorBreakdown({ rows, threshold = 3 }: FactorBreakdownProps) {
  const sum = rows ? sumFactorScores(rows) : 0;
  return (
    <div className="factor-card">
      <div className="factor-card__header">
        <h3 className="factor-card__title">판정 근거 (기여요인)</h3>
        <span className="factor-card__meta">지표별 점수</span>
      </div>

      {rows === null ? (
        <p className="factor-card__empty">데이터 부족으로 분해할 수 없습니다.</p>
      ) : (
        <>
          <ul className="factor-list">
            {rows.map((row) => {
              const pct = Math.min(50, (Math.abs(row.score) / row.maxAbs) * 50);
              const color = scoreColor(row.score);
              return (
                <li key={row.key} className="factor-row" title={row.rule}>
                  <div className="factor-row__top">
                    <span className="factor-row__label">{row.label}</span>
                    <span className="factor-row__score" style={{ color }}>
                      {row.score > 0 ? `+${row.score}` : row.score}
                    </span>
                  </div>
                  <div
                    className="factor-row__bar"
                    role="img"
                    aria-label={`${row.label} 기여 점수 ${row.score > 0 ? "+" : ""}${row.score} — ${row.rule}`}
                  >
                    <span className="factor-row__center-line" aria-hidden="true" />
                    {row.score !== 0 ? (
                      <span
                        className={`factor-row__fill ${
                          row.score > 0 ? "factor-row__fill--pos" : "factor-row__fill--neg"
                        }`}
                        style={
                          row.score > 0
                            ? { left: "50%", width: `${pct}%` }
                            : { right: "50%", width: `${pct}%` }
                        }
                        aria-hidden="true"
                      />
                    ) : null}
                  </div>
                  <span className="factor-row__rule">{row.rule}</span>
                </li>
              );
            })}
          </ul>
          <p className="factor-card__summary">
            합계 <b>{sum > 0 ? `+${sum}` : sum}점</b> · 합계가 <b>+{threshold} 이상</b>이면 매수,{" "}
            <b>−{threshold} 이하</b>면 매도로 판정합니다.
          </p>
        </>
      )}
    </div>
  );
}
