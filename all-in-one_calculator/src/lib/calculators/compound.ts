export type CompoundFrequency = "daily" | "monthly" | "yearly";

export interface CompoundInput {
  principal: number;
  monthlyContribution: number;
  annualRate: number;
  years: number;
  frequency: CompoundFrequency;
}

export interface YearlyBreakdown {
  year: number;
  balance: number;
  totalDeposit: number;
  totalInterest: number;
}

export interface CompoundResult {
  finalAmount: number;
  totalDeposit: number;
  totalInterest: number;
  yearlyBreakdown: YearlyBreakdown[];
}

const frequencyMap: Record<CompoundFrequency, number> = {
  daily: 365,
  monthly: 12,
  yearly: 1,
};

export function calculateCompound(input: CompoundInput): CompoundResult {
  const { principal, monthlyContribution, annualRate, years, frequency } = input;
  const n = frequencyMap[frequency];
  const r = annualRate / 100;
  const ratePerPeriod = r / n;

  const yearlyBreakdown: YearlyBreakdown[] = [];
  let balance = principal;
  let totalDeposit = principal;

  for (let year = 1; year <= years; year++) {
    for (let period = 0; period < n; period++) {
      // Add interest
      balance *= 1 + ratePerPeriod;

      // Add monthly contributions proportionally
      if (frequency === "daily") {
        balance += monthlyContribution / 30;
        totalDeposit += monthlyContribution / 30;
      } else if (frequency === "monthly") {
        balance += monthlyContribution;
        totalDeposit += monthlyContribution;
      } else {
        balance += monthlyContribution * 12;
        totalDeposit += monthlyContribution * 12;
      }
    }

    yearlyBreakdown.push({
      year,
      balance: Math.round(balance),
      totalDeposit: Math.round(totalDeposit),
      totalInterest: Math.round(balance - totalDeposit),
    });
  }

  return {
    finalAmount: Math.round(balance),
    totalDeposit: Math.round(totalDeposit),
    totalInterest: Math.round(balance - totalDeposit),
    yearlyBreakdown,
  };
}
