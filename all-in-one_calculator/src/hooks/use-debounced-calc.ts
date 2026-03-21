"use client";

import { useState, useEffect, useRef } from "react";

export function useDebouncedCalc<TInput, TOutput>(
  calcFn: (input: TInput) => TOutput,
  input: TInput,
  debounceMs = 300
): { result: TOutput | null; isCalculating: boolean } {
  const [result, setResult] = useState<TOutput | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    setIsCalculating(true);

    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    timeoutRef.current = setTimeout(() => {
      try {
        const output = calcFn(input);
        setResult(output);
      } catch {
        // keep previous result on error
      }
      setIsCalculating(false);
    }, debounceMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [calcFn, input, debounceMs]);

  return { result, isCalculating };
}
