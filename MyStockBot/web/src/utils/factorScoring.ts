// MACD/RSI/재무 지표 라벨 → 기여 점수 매핑.
// MyStockBot/src/indicators.py 의 _macd_score / _rsi_score / _fundamental_score 규칙과 동일하게 유지할 것.

import type { SnapshotFactors } from "../types";

export function macdScore(label: string | null): number {
  switch (label) {
    case "골든크로스(진입)":
      return 2;
    case "진입구간":
      return 1;
    case "매도구간":
      return -1;
    case "데드크로스(매도)":
      return -2;
    default:
      return 0;
  }
}

export function rsiScore(label: string | null): number {
  switch (label) {
    case "과매도(진입)":
      return 1;
    case "과매수(매도)":
      return -1;
    default:
      return 0;
  }
}

export function perScore(per: number | null): number {
  if (per === null) return 0;
  if (per <= 0) return -1;
  if (per < 10) return 1;
  if (per >= 30) return -1;
  return 0;
}

export function pbrScore(pbr: number | null): number {
  if (pbr === null || pbr <= 0) return 0;
  if (pbr < 1) return 1;
  if (pbr >= 3) return -1;
  return 0;
}

export function roeScore(roe: number | null): number {
  if (roe === null) return 0;
  if (roe >= 15) return 1;
  if (roe < 0) return -1;
  return 0;
}

export interface FactorRow {
  key: string;
  /** 지표 라벨 + (있다면) 수치 — 예: "MACD 골든크로스(진입)", "RSI 중립 · RSI 52.4" */
  label: string;
  score: number;
  /** 기여 바 폭 계산용 — 해당 지표가 가질 수 있는 점수 절대값의 최댓값 */
  maxAbs: number;
  /** 이 점수가 왜 나왔는지 사람말 설명 — 예: "골든크로스 — 강한 진입(+2)" */
  rule: string;
}

/** 지표별 점수 산정 규칙을 사람이 읽는 한 줄로. indicators.py 규칙과 동일 기준. */
export function ruleText(key: string, score: number): string {
  switch (key) {
    case "macd":
      return score === 2
        ? "골든크로스 — 강한 진입 (+2)"
        : score === 1
          ? "MACD > 시그널 — 진입구간 (+1)"
          : score === -1
            ? "MACD < 시그널 — 매도구간 (−1)"
            : score === -2
              ? "데드크로스 — 강한 매도 (−2)"
              : "판정 불가 (0)";
    case "rsi":
      return score > 0 ? "과매도 — 반등 기대 (+1)" : score < 0 ? "과매수 — 조정 주의 (−1)" : "30~70 중립 (0)";
    case "per":
      return score > 0 ? "PER < 10 — 저평가 (+1)" : score < 0 ? "PER ≥ 30·적자 — 부담 (−1)" : "보통 (0)";
    case "pbr":
      return score > 0 ? "PBR < 1 — 자산 저평가 (+1)" : score < 0 ? "PBR ≥ 3 — 고평가 (−1)" : "보통 (0)";
    case "roe":
      return score > 0 ? "ROE ≥ 15% — 고수익성 (+1)" : score < 0 ? "ROE < 0 — 적자 (−1)" : "보통 (0)";
    default:
      return "";
  }
}

function formatNumber(value: number | null, digits: number, suffix = ""): string {
  return value !== null ? `${value.toFixed(digits)}${suffix}` : "데이터부족";
}

/** 단기(60분봉) 기여요인 분해 — MACD·RSI */
function buildShortRows(factors: SnapshotFactors): FactorRow[] {
  const macdLabel = factors.macd_60m ?? "데이터부족";
  const rsiZone = factors.rsi_60m ?? "데이터부족";
  const rsiValueText =
    factors.rsi_value_60m !== null ? ` · RSI ${factors.rsi_value_60m.toFixed(1)}` : "";

  return [
    {
      key: "macd",
      label: `MACD ${macdLabel}`,
      score: macdScore(factors.macd_60m),
      maxAbs: 2,
      rule: ruleText("macd", macdScore(factors.macd_60m)),
    },
    {
      key: "rsi",
      label: `RSI ${rsiZone}${rsiValueText}`,
      score: rsiScore(factors.rsi_60m),
      maxAbs: 1,
      rule: ruleText("rsi", rsiScore(factors.rsi_60m)),
    },
  ];
}

/** 장기(일봉+재무) 기여요인 분해 — MACD·RSI·PER·PBR·ROE */
function buildLongRows(factors: SnapshotFactors): FactorRow[] {
  const macdLabel = factors.macd_1d ?? "데이터부족";
  const rsiZone = factors.rsi_1d ?? "데이터부족";
  const rsiValueText =
    factors.rsi_value_1d !== null ? ` · RSI ${factors.rsi_value_1d.toFixed(1)}` : "";

  return [
    {
      key: "macd",
      label: `MACD ${macdLabel}`,
      score: macdScore(factors.macd_1d),
      maxAbs: 2,
      rule: ruleText("macd", macdScore(factors.macd_1d)),
    },
    {
      key: "rsi",
      label: `RSI ${rsiZone}${rsiValueText}`,
      score: rsiScore(factors.rsi_1d),
      maxAbs: 1,
      rule: ruleText("rsi", rsiScore(factors.rsi_1d)),
    },
    {
      key: "per",
      label: `PER ${formatNumber(factors.per, 1, "배")}`,
      score: perScore(factors.per),
      maxAbs: 1,
      rule: ruleText("per", perScore(factors.per)),
    },
    {
      key: "pbr",
      label: `PBR ${formatNumber(factors.pbr, 2, "배")}`,
      score: pbrScore(factors.pbr),
      maxAbs: 1,
      rule: ruleText("pbr", pbrScore(factors.pbr)),
    },
    {
      key: "roe",
      label: `ROE ${formatNumber(factors.roe, 1, "%")}`,
      score: roeScore(factors.roe),
      maxAbs: 1,
      rule: ruleText("roe", roeScore(factors.roe)),
    },
  ];
}

export function buildFactorRows(
  factors: SnapshotFactors,
  view: "short" | "long"
): FactorRow[] {
  return view === "short" ? buildShortRows(factors) : buildLongRows(factors);
}

/** 개별 기여 점수 합. 백엔드 factors.short_score/long_score와 불일치할 수 있으므로
 * 화면 표기(게이지 캡션 등)는 항상 이 합계를 우선 사용한다. */
export function sumFactorScores(rows: FactorRow[]): number {
  return rows.reduce((sum, row) => sum + row.score, 0);
}
