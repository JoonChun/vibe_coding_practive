import { TrendingUp, Landmark, Wallet, ArrowLeftRight, Calendar } from "lucide-react";

export type ReportCategory = "growth" | "cost" | "net" | "general";

export interface CategoryInfo {
  id: ReportCategory;
  label: string;
  icon: typeof TrendingUp;
  color: string;
}

export const REPORT_CATEGORIES: Record<ReportCategory, CategoryInfo> = {
  growth: {
    id: "growth",
    label: "성장성 및 자산",
    icon: TrendingUp,
    color: "text-emerald-500",
  },
  cost: {
    id: "cost",
    label: "지출 및 비용",
    icon: Landmark,
    color: "text-rose-500",
  },
  net: {
    id: "net",
    label: "실수령액 및 수익",
    icon: Wallet,
    color: "text-amber-500",
  },
  general: {
    id: "general",
    label: "일반 및 기타",
    icon: ArrowLeftRight,
    color: "text-blue-500",
  },
};
