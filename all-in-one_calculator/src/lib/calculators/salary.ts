import {
  NATIONAL_PENSION_RATE,
  NATIONAL_PENSION_MAX_MONTHLY,
  HEALTH_INSURANCE_RATE,
  LONG_TERM_CARE_RATE,
  EMPLOYMENT_INSURANCE_RATE,
  INCOME_TAX_BRACKETS,
  LOCAL_INCOME_TAX_RATE,
  EARNED_INCOME_DEDUCTION_BRACKETS,
  PERSONAL_DEDUCTION_PER_PERSON,
} from "@/lib/constants";

export interface SalaryInput {
  annualSalary: number;
  dependents: number;
  nonTaxableAllowance: number;
}

export interface DeductionItem {
  name: string;
  monthlyAmount: number;
  annualAmount: number;
}

export interface SalaryResult {
  monthlyGross: number;
  monthlyNet: number;
  annualNet: number;
  deductions: DeductionItem[];
  totalMonthlyDeduction: number;
}

function calcEarnedIncomeDeduction(totalPay: number): number {
  for (const bracket of EARNED_INCOME_DEDUCTION_BRACKETS) {
    if (totalPay <= bracket.limit) {
      return bracket.prev + (totalPay - (bracket.prev > 0 ? EARNED_INCOME_DEDUCTION_BRACKETS[EARNED_INCOME_DEDUCTION_BRACKETS.indexOf(bracket) - 1]?.limit ?? 0 : 0)) * bracket.rate;
    }
  }
  return 0;
}

function calcIncomeTax(taxableIncome: number): number {
  if (taxableIncome <= 0) return 0;
  for (const bracket of INCOME_TAX_BRACKETS) {
    if (taxableIncome <= bracket.limit) {
      return taxableIncome * bracket.rate - bracket.deduction;
    }
  }
  return 0;
}

export function calculateSalary(input: SalaryInput): SalaryResult {
  const { annualSalary, dependents, nonTaxableAllowance } = input;
  const monthlyGross = Math.round(annualSalary / 12);
  const monthlyTaxable = monthlyGross - nonTaxableAllowance;
  const annualTaxable = monthlyTaxable * 12;

  // 4대 보험 (월 기준)
  const nationalPension = Math.min(
    monthlyTaxable * NATIONAL_PENSION_RATE,
    NATIONAL_PENSION_MAX_MONTHLY
  );
  const healthInsurance = monthlyTaxable * HEALTH_INSURANCE_RATE;
  const longTermCare = healthInsurance * LONG_TERM_CARE_RATE;
  const employmentInsurance = monthlyTaxable * EMPLOYMENT_INSURANCE_RATE;

  // 소득세 (연간 → 월할)
  const earnedDeduction = calcEarnedIncomeDeduction(annualTaxable);
  const personalDeduction = PERSONAL_DEDUCTION_PER_PERSON * Math.max(dependents, 1);
  const taxableIncome = Math.max(annualTaxable - earnedDeduction - personalDeduction, 0);
  const annualIncomeTax = calcIncomeTax(taxableIncome);
  const monthlyIncomeTax = annualIncomeTax / 12;
  const monthlyLocalTax = monthlyIncomeTax * LOCAL_INCOME_TAX_RATE;

  const deductions: DeductionItem[] = [
    { name: "국민연금", monthlyAmount: Math.round(nationalPension), annualAmount: Math.round(nationalPension * 12) },
    { name: "건강보험", monthlyAmount: Math.round(healthInsurance), annualAmount: Math.round(healthInsurance * 12) },
    { name: "장기요양보험", monthlyAmount: Math.round(longTermCare), annualAmount: Math.round(longTermCare * 12) },
    { name: "고용보험", monthlyAmount: Math.round(employmentInsurance), annualAmount: Math.round(employmentInsurance * 12) },
    { name: "소득세", monthlyAmount: Math.round(monthlyIncomeTax), annualAmount: Math.round(annualIncomeTax) },
    { name: "지방소득세", monthlyAmount: Math.round(monthlyLocalTax), annualAmount: Math.round(monthlyLocalTax * 12) },
  ];

  const totalMonthlyDeduction = deductions.reduce((sum, d) => sum + d.monthlyAmount, 0);
  const monthlyNet = monthlyGross - totalMonthlyDeduction;

  return {
    monthlyGross,
    monthlyNet,
    annualNet: monthlyNet * 12,
    deductions,
    totalMonthlyDeduction,
  };
}
