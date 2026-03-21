import type { CalculationResult } from "@/types/calculator";
import { formatCurrency } from "@/lib/utils";

export interface ComparisonField {
  field: string;
  label: string;
  values: (number | string)[];
  winnerIndex: number | null;
  higherIsBetter: boolean;
}

export interface ComparisonReport {
  items: CalculationResult[];
  fields: ComparisonField[];
  insight: string;
}

const OUTPUT_LABELS: Record<string, { label: string; higherIsBetter: boolean }> = {
  finalAmount: { label: "최종 금액", higherIsBetter: true },
  totalDeposit: { label: "총 적립액", higherIsBetter: false },
  totalInterest: { label: "이자 수익", higherIsBetter: true },
  monthlyPayment: { label: "월 상환액", higherIsBetter: false },
  totalPayment: { label: "총 상환액", higherIsBetter: false },
  monthlyNet: { label: "월 실수령액", higherIsBetter: true },
  annualNet: { label: "연 실수령액", higherIsBetter: true },
  totalMonthlyDeduction: { label: "월 공제 합계", higherIsBetter: false },
};

export function generateComparison(items: CalculationResult[]): ComparisonReport {
  if (items.length < 2) {
    return { items, fields: [], insight: "비교하려면 2개 이상의 결과를 선택하세요." };
  }

  // Find common output keys
  const allKeys = items.map((item) => Object.keys(item.outputs));
  const commonKeys = allKeys[0].filter((key) =>
    allKeys.every((keys) => keys.includes(key))
  );

  const fields: ComparisonField[] = commonKeys
    .filter((key) => OUTPUT_LABELS[key])
    .map((key) => {
      const config = OUTPUT_LABELS[key];
      const values = items.map((item) => item.outputs[key]);
      const numericValues = values.map(Number);

      let winnerIndex: number | null = null;
      if (numericValues.every((v) => !isNaN(v))) {
        if (config.higherIsBetter) {
          winnerIndex = numericValues.indexOf(Math.max(...numericValues));
        } else {
          winnerIndex = numericValues.indexOf(Math.min(...numericValues));
        }
        // No winner if all values are the same
        if (numericValues.every((v) => v === numericValues[0])) {
          winnerIndex = null;
        }
      }

      return {
        field: key,
        label: config.label,
        values,
        winnerIndex,
        higherIsBetter: config.higherIsBetter,
      };
    });

  // Generate insight
  let insight = "";
  const primaryField = fields[0];
  if (primaryField && primaryField.winnerIndex !== null) {
    const winnerLabel = items[primaryField.winnerIndex].label;
    const values = primaryField.values.map(Number);
    const diff = Math.abs(values[0] - values[1]);
    const winnerName = `시나리오 ${String.fromCharCode(65 + primaryField.winnerIndex)}`;
    insight = `${winnerName}(${winnerLabel})이 ${primaryField.label} 기준으로 ${formatCurrency(diff)} 유리합니다.`;
  }

  return { items, fields, insight };
}
