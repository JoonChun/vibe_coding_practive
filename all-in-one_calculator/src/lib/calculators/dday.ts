import { differenceInDays, differenceInMonths, differenceInYears, addDays, addMonths, addYears, format } from "date-fns";
import { ko } from "date-fns/locale";

export interface DdayEvent {
  id: string;
  name: string;
  targetDate: string; // ISO date string
}

export interface DdayBreakdown {
  years: number;
  months: number;
  days: number;
}

export interface DdayResult {
  daysRemaining: number;
  breakdown: DdayBreakdown;
  targetDateFormatted: string;
  isPast: boolean;
}

export function calculateDday(targetDate: string): DdayResult {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(targetDate);
  target.setHours(0, 0, 0, 0);

  const daysRemaining = differenceInDays(target, today);

  // 년/월/일 분해: 항상 과거→미래 방향으로 계산
  const [from, to] = daysRemaining >= 0 ? [today, target] : [target, today];
  const yrs = differenceInYears(to, from);
  const afterYears = addYears(from, yrs);
  const mos = differenceInMonths(to, afterYears);
  const afterMonths = addMonths(afterYears, mos);
  const dys = differenceInDays(to, afterMonths);

  return {
    daysRemaining,
    breakdown: { years: yrs, months: mos, days: dys },
    targetDateFormatted: format(target, "yyyy년 MM월 dd일 (EEEE)", {
      locale: ko,
    }),
    isPast: daysRemaining < 0,
  };
}

export function calculateDateFromDays(days: number): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = addDays(today, days);
  return format(target, "yyyy-MM-dd");
}

export function formatDdayDisplay(days: number): string {
  if (days === 0) return "D-Day";
  if (days > 0) return `D-${days}`;
  return `D+${Math.abs(days)}`;
}

export function formatBreakdown(b: DdayBreakdown): string {
  const parts: string[] = [];
  if (b.years > 0) parts.push(`${b.years}년`);
  if (b.months > 0) parts.push(`${b.months}개월`);
  if (b.days > 0 || parts.length === 0) parts.push(`${b.days}일`);
  return parts.join(" ");
}
