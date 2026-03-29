"use client";

import { useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useCalculatorStore } from "@/stores/calculator-store";

export function useRestore(
  applyInputs: (inputs: Record<string, number | string>) => void
) {
  const searchParams = useSearchParams();
  const restoreId = searchParams.get("restore");
  const results = useCalculatorStore((s) => s.results);
  const appliedRef = useRef(false);

  useEffect(() => {
    if (!restoreId || appliedRef.current) return;
    const saved = results[restoreId];
    if (saved) {
      applyInputs(saved.inputs);
      appliedRef.current = true;
    }
  }, [restoreId, results, applyInputs]);

  return restoreId;
}
