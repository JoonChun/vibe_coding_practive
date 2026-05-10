export type CalculatorType =
  | "compound"
  | "loan"
  | "salary"
  | "unit"
  | "dday"
  | "bmi";

export interface CalculationResult {
  id: string;
  type: CalculatorType;
  label: string;
  inputs: Record<string, number | string>;
  outputs: Record<string, number | string>;
  timestamp: number;
}

export interface PinnedItem {
  resultId: string;
  displayKey: string;
}

export const CALCULATOR_LABELS: Record<CalculatorType, string> = {
  compound: "복리/적금 계산기",
  loan: "대출 상환 계산기",
  salary: "연봉 실수령액",
  unit: "단위 변환",
  dday: "디데이 계산기",
  bmi: "BMI 계산기",
};
