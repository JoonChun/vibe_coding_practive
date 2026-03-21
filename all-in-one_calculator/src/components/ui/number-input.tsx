"use client";

import { useCallback, useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface NumberInputProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
  label?: string;
}

export function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
  className,
}: NumberInputProps) {
  const [error, setError] = useState<string | null>(null);
  const formatted = value.toLocaleString("ko-KR");

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value.replace(/[^0-9.\-]/g, "");
      if (raw === "" || raw === "-") {
        onChange(0);
        setError(null);
        return;
      }
      let num = parseFloat(raw);
      if (isNaN(num)) return;

      if (min !== undefined && num < min) {
        num = min;
        setError(`최솟값은 ${min.toLocaleString("ko-KR")}입니다`);
        setTimeout(() => setError(null), 2000);
      } else if (max !== undefined && num > max) {
        num = max;
        setError(`최댓값은 ${max.toLocaleString("ko-KR")}입니다`);
        setTimeout(() => setError(null), 2000);
      } else {
        setError(null);
      }
      onChange(num);
    },
    [onChange, min, max]
  );

  return (
    <div className="space-y-1">
      <Input
        type="text"
        inputMode="decimal"
        value={formatted}
        onChange={handleChange}
        step={step}
        className={cn(
          "font-mono",
          error && "border-destructive focus-visible:ring-destructive",
          className
        )}
      />
      {error && (
        <p className="text-xs text-destructive animate-in fade-in slide-in-from-top-1 duration-200">
          {error}
        </p>
      )}
    </div>
  );
}
