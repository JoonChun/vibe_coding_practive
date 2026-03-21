export type RepaymentMethod = "equal-payment" | "equal-principal" | "bullet";

export interface LoanInput {
  loanAmount: number;
  annualRate: number;
  termMonths: number;
  method: RepaymentMethod;
}

export interface MonthlySchedule {
  month: number;
  payment: number;
  principal: number;
  interest: number;
  remainingBalance: number;
}

export interface LoanResult {
  monthlyPayment: number;
  totalPayment: number;
  totalInterest: number;
  schedule: MonthlySchedule[];
}

export function calculateLoan(input: LoanInput): LoanResult {
  const { loanAmount, annualRate, termMonths, method } = input;
  const monthlyRate = annualRate / 100 / 12;

  switch (method) {
    case "equal-payment":
      return calcEqualPayment(loanAmount, monthlyRate, termMonths);
    case "equal-principal":
      return calcEqualPrincipal(loanAmount, monthlyRate, termMonths);
    case "bullet":
      return calcBullet(loanAmount, monthlyRate, termMonths);
  }
}

function calcEqualPayment(
  P: number,
  r: number,
  n: number
): LoanResult {
  const monthlyPayment =
    r === 0 ? P / n : (P * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);

  const schedule: MonthlySchedule[] = [];
  let remaining = P;

  for (let month = 1; month <= n; month++) {
    const interest = remaining * r;
    const principal = monthlyPayment - interest;
    remaining -= principal;

    schedule.push({
      month,
      payment: Math.round(monthlyPayment),
      principal: Math.round(principal),
      interest: Math.round(interest),
      remainingBalance: Math.max(0, Math.round(remaining)),
    });
  }

  const totalPayment = Math.round(monthlyPayment * n);
  return {
    monthlyPayment: Math.round(monthlyPayment),
    totalPayment,
    totalInterest: totalPayment - P,
    schedule,
  };
}

function calcEqualPrincipal(
  P: number,
  r: number,
  n: number
): LoanResult {
  const principalPerMonth = P / n;
  const schedule: MonthlySchedule[] = [];
  let remaining = P;
  let totalPayment = 0;

  for (let month = 1; month <= n; month++) {
    const interest = remaining * r;
    const payment = principalPerMonth + interest;
    remaining -= principalPerMonth;
    totalPayment += payment;

    schedule.push({
      month,
      payment: Math.round(payment),
      principal: Math.round(principalPerMonth),
      interest: Math.round(interest),
      remainingBalance: Math.max(0, Math.round(remaining)),
    });
  }

  return {
    monthlyPayment: Math.round(schedule[0]?.payment ?? 0),
    totalPayment: Math.round(totalPayment),
    totalInterest: Math.round(totalPayment - P),
    schedule,
  };
}

function calcBullet(
  P: number,
  r: number,
  n: number
): LoanResult {
  const monthlyInterest = P * r;
  const schedule: MonthlySchedule[] = [];

  for (let month = 1; month <= n; month++) {
    const isLast = month === n;
    schedule.push({
      month,
      payment: Math.round(isLast ? monthlyInterest + P : monthlyInterest),
      principal: Math.round(isLast ? P : 0),
      interest: Math.round(monthlyInterest),
      remainingBalance: Math.round(isLast ? 0 : P),
    });
  }

  const totalPayment = Math.round(monthlyInterest * n + P);
  return {
    monthlyPayment: Math.round(monthlyInterest),
    totalPayment,
    totalInterest: Math.round(monthlyInterest * n),
    schedule,
  };
}
