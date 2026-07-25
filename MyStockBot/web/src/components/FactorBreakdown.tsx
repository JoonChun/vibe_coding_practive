import type { DecisionRules, FactorRow } from "../types";

interface FactorBreakdownProps {
  /** 백엔드가 계산한 기여요인 행. null 이면 분해 불가(수집 실패·데이터부족). */
  rows: FactorRow[] | null;
  /** 판정 임계값(스냅샷 응답의 rules). 없으면 규칙 설명 캡션을 생략한다. */
  rules?: DecisionRules | null;
  /** "short" | "long" — 어느 쪽 임계값을 설명할지 */
  view: "short" | "long";
}

function scoreColor(score: number): string {
  if (score > 0) return "#16a34a";
  if (score < 0) return "#dc2626";
  return "#6b7280";
}

/**
 * 판정 규칙 설명 문구.
 *
 * 예전 캡션은 "합계가 +{threshold} 이상이면 매수, −{threshold} 이하면 매도"였는데 이는
 * **틀린 설명**이었다. 실제 규칙은 `weak`(=1) 이상이면 매수이고 `strong`(단기 2·장기 3)
 * 이상이면 강력매수다. 규칙을 설명하려고 넣은 캡션이 규칙을 잘못 말하고 있었다.
 */
function ruleCaption(rules: DecisionRules, view: "short" | "long"): string {
  const strong = view === "short" ? rules.short_strong : rules.long_strong;
  const base = `합계 +${rules.weak} 이상이면 매수, +${strong} 이상이면 강력매수 (매도는 반대 방향 동일)`;
  if (view === "long" && rules.long_strong_requires_tech_confirm) {
    return `${base}. 단, 강력 등급은 MACD·RSI 기술 점수가 같은 방향일 때만 부여합니다 — 재무 지표만으로는 강력 등급이 나오지 않습니다.`;
  }
  return `${base}.`;
}

/** 기여요인 분해 — 중앙 0선 기준 좌(음수·빨강)/우(양수·초록) Tug-of-War 바 */
export function FactorBreakdown({ rows, rules, view }: FactorBreakdownProps) {
  const sum = rows ? rows.reduce((acc, row) => acc + row.score, 0) : 0;
  return (
    <div className="factor-card">
      <div className="factor-card__header">
        <h3 className="factor-card__title">판정 근거 (기여요인)</h3>
        <span className="factor-card__meta">지표별 점수</span>
      </div>

      {rows === null || rows.length === 0 ? (
        <p className="factor-card__empty">데이터 부족으로 분해할 수 없습니다.</p>
      ) : (
        <>
          <ul className="factor-list">
            {rows.map((row) => {
              const pct = Math.min(50, (Math.abs(row.score) / row.max_abs) * 50);
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
            합계 <b>{sum > 0 ? `+${sum}` : sum}점</b>
            {rules ? <> · {ruleCaption(rules, view)}</> : null}
          </p>
        </>
      )}
    </div>
  );
}
