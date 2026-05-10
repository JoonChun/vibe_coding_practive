"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  TrendingUp,
  Landmark,
  Wallet,
  ArrowLeftRight,
  Calendar,
  BarChart3,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/calculators/compound", label: "복리/적금", icon: TrendingUp },
  { href: "/calculators/loan", label: "대출 상환", icon: Landmark },
  { href: "/calculators/salary", label: "연봉 실수령액", icon: Wallet },
  { href: "/calculators/unit", label: "단위 변환", icon: ArrowLeftRight },
  { href: "/calculators/dday", label: "디데이", icon: Calendar },
  { href: "/calculators/bmi", label: "BMI", icon: Activity },
  { href: "/report", label: "비교 리포트", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex lg:flex-col lg:w-60 lg:fixed lg:inset-y-0 border-r border-border bg-card">
      <div className="flex items-center h-16 px-6 border-b border-border">
        <h1 className="text-lg font-bold text-primary">Life Calc</h1>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
