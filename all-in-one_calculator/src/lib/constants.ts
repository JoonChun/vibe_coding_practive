// 2024-2025 기준 세율/보험료율 (최종 업데이트: 2025-01)

export const NATIONAL_PENSION_RATE = 0.045;
export const NATIONAL_PENSION_MAX_MONTHLY = 590_000 * 0.045; // 상한 기준 소득월액 590만원

export const HEALTH_INSURANCE_RATE = 0.03545;
export const LONG_TERM_CARE_RATE = 0.1281; // 건강보험료의 12.81%

export const EMPLOYMENT_INSURANCE_RATE = 0.009;

// 소득세 구간 (과세표준 기준)
export const INCOME_TAX_BRACKETS = [
  { limit: 14_000_000, rate: 0.06, deduction: 0 },
  { limit: 50_000_000, rate: 0.15, deduction: 1_260_000 },
  { limit: 88_000_000, rate: 0.24, deduction: 5_760_000 },
  { limit: 150_000_000, rate: 0.35, deduction: 15_440_000 },
  { limit: 300_000_000, rate: 0.38, deduction: 19_940_000 },
  { limit: 500_000_000, rate: 0.40, deduction: 25_940_000 },
  { limit: 1_000_000_000, rate: 0.42, deduction: 35_940_000 },
  { limit: Infinity, rate: 0.45, deduction: 65_940_000 },
] as const;

export const LOCAL_INCOME_TAX_RATE = 0.1; // 소득세의 10%

// 근로소득공제
export const EARNED_INCOME_DEDUCTION_BRACKETS = [
  { limit: 5_000_000, rate: 0.7, prev: 0 },
  { limit: 15_000_000, rate: 0.4, prev: 3_500_000 },
  { limit: 45_000_000, rate: 0.15, prev: 7_500_000 },
  { limit: 100_000_000, rate: 0.05, prev: 12_000_000 },
  { limit: Infinity, rate: 0.02, prev: 14_750_000 },
] as const;

// 인적공제 기본 (1인당 150만원)
export const PERSONAL_DEDUCTION_PER_PERSON = 1_500_000;
