"use client";

import { useEffect, useRef, useState } from "react";
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
  const [text, setText] = useState(value.toLocaleString("ko-KR"));
  const [error, setError] = useState<string | null>(null);
  const isFocused = useRef(false);

  // 외부 value가 바뀌면 표시 갱신 — 포커스 중엔 무시
  useEffect(() => {
    if (!isFocused.current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setText(value.toLocaleString("ko-KR"));
    }
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setText(e.target.value); // 자유 입력, clamp 없음
  };

  const handleFocus = () => {
    isFocused.current = true;
  };

  const handleBlur = () => {
    isFocused.current = false;

    const raw = text.replace(/[^0-9.\-]/g, "");

    if (raw === "" || raw === "-") {
      const fallback = min ?? 0;
      setText(fallback.toLocaleString("ko-KR"));
      onChange(fallback);
      return;
    }

    const num = parseFloat(raw);

    if (isNaN(num)) {
      setText(value.toLocaleString("ko-KR"));
      return;
    }

    let clamped = num;

    if (min !== undefined && num < min) {
      clamped = min;
      setError(`최솟값은 ${min.toLocaleString("ko-KR")}입니다`);
      setTimeout(() => setError(null), 2000);
    } else if (max !== undefined && num > max) {
      clamped = max;
      setError(`최댓값은 ${max.toLocaleString("ko-KR")}입니다`);
      setTimeout(() => setError(null), 2000);
    } else {
      setError(null);
    }

    setText(clamped.toLocaleString("ko-KR"));
    onChange(clamped);
  };

  return (
    <div className="space-y-1">
      <Input
        type="text"
        inputMode="decimal"
        value={text}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
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
