"use client";

import { formatCurrency } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface ChartTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string | number;
  titleSuffix?: string;
  valueFormatter?: (value: number) => string;
}

export function ChartTooltip({
  active,
  payload,
  label,
  titleSuffix = "년차",
  valueFormatter = formatCurrency,
}: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/80 p-3 shadow-2xl backdrop-blur-md ring-1 ring-white/20">
      <div className="mb-2 border-b border-white/5 pb-1.5">
        <p className="text-[11px] font-black uppercase tracking-wider text-slate-400">
          {label}{titleSuffix}
        </p>
      </div>
      <div className="space-y-1.5">
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div 
                className="h-1.5 w-1.5 rounded-full" 
                style={{ backgroundColor: entry.color || entry.fill }} 
              />
              <span className="text-xs font-medium text-slate-300">
                {entry.name}
              </span>
            </div>
            <span className="text-xs font-bold font-mono text-white">
              {valueFormatter(entry.value)}
            </span>
          </div>
        ))}
      </div>
      
      {/* Optional: Add summary/total if multiple items exist */}
      {payload.length > 1 && (
        <div className="mt-2 border-t border-white/5 pt-1.5 flex justify-between items-center gap-4">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">Total</span>
          <span className="text-xs font-black text-emerald-400 font-mono">
            {valueFormatter(payload.reduce((acc, curr) => acc + Number(curr.value), 0))}
          </span>
        </div>
      )}
    </div>
  );
}
