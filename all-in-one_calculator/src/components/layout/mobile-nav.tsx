"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Calculator,
  BarChart3,
  TrendingUp,
  Landmark,
  Wallet,
  ArrowLeftRight,
  Calendar,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const calcLinks = [
  { href: "/calculators/compound", label: "복리/적금", icon: TrendingUp },
  { href: "/calculators/loan", label: "대출 상환", icon: Landmark },
  { href: "/calculators/salary", label: "연봉 실수령", icon: Wallet },
  { href: "/calculators/unit", label: "단위 변환", icon: ArrowLeftRight },
  { href: "/calculators/dday", label: "디데이", icon: Calendar },
];

export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isCalcActive = pathname.startsWith("/calculators");

  return (
    <>
      {/* Overlay grid menu */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-border">
            <h2 className="text-lg font-bold">계산기</h2>
            <button onClick={() => setOpen(false)}>
              <X className="h-6 w-6 text-muted-foreground" />
            </button>
          </div>
          <div className="flex-1 p-4">
            <div className="grid grid-cols-2 gap-3">
              {calcLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex flex-col items-center gap-2 p-4 rounded-xl border transition-colors",
                    pathname === link.href
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border hover:bg-accent"
                  )}
                >
                  <link.icon className="h-6 w-6" />
                  <span className="text-sm font-medium">{link.label}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-border bg-card/95 backdrop-blur-sm">
        <div className="flex items-center justify-around h-16">
          <Link
            href="/"
            className={cn(
              "flex flex-col items-center gap-1 px-3 py-1.5 text-xs font-medium transition-colors",
              pathname === "/" ? "text-primary" : "text-muted-foreground"
            )}
          >
            <LayoutDashboard className="h-5 w-5" />
            대시보드
          </Link>

          <button
            onClick={() => setOpen(true)}
            className={cn(
              "flex flex-col items-center gap-1 px-3 py-1.5 text-xs font-medium transition-colors",
              isCalcActive ? "text-primary" : "text-muted-foreground"
            )}
          >
            <Calculator className="h-5 w-5" />
            계산기
          </button>

          <Link
            href="/report"
            className={cn(
              "flex flex-col items-center gap-1 px-3 py-1.5 text-xs font-medium transition-colors",
              pathname === "/report" ? "text-primary" : "text-muted-foreground"
            )}
          >
            <BarChart3 className="h-5 w-5" />
            리포트
          </Link>
        </div>
      </nav>
    </>
  );
}
