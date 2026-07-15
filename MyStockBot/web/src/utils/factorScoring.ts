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
    },
    {
      key: "rsi",
      label: `RSI ${rsiZone}${rsiValueText}`,
      score: rsiScore(factors.rsi_60m),
      maxAbs: 1,
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
    },
    {
      key: "rsi",
      label: `RSI ${rsiZone}${rsiValueText}`,
      score: rsiScore(factors.rsi_1d),
      maxAbs: 1,
    },
    {
      key: "per",
      label: `PER ${formatNumber(factors.per, 1, "배")}`,
      score: perScore(factors.per),
      maxAbs: 1,
    },
    {
      key: "pbr",
      label: `PBR ${formatNumber(factors.pbr, 2, "배")}`,
      score: pbrScore(factors.pbr),
      maxAbs: 1,
    },
    {
      key: "roe",
      label: `ROE ${formatNumber(factors.roe, 1, "%")}`,
      score: roeScore(factors.roe),
      maxAbs: 1,
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
