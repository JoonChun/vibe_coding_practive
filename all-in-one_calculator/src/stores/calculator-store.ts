"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CalculationResult } from "@/types/calculator";

interface CalculatorStore {
  results: Record<string, CalculationResult>;
  setResult: (result: CalculationResult) => void;
  removeResult: (id: string) => void;
  getResultsByType: (type: string) => CalculationResult[];
}

export const useCalculatorStore = create<CalculatorStore>()(
  persist(
    (set, get) => ({
      results: {},
      setResult: (result) =>
        set((state) => ({
          results: { ...state.results, [result.id]: result },
        })),
      removeResult: (id) =>
        set((state) => {
          const { [id]: _, ...rest } = state.results;
          return { results: rest };
        }),
      getResultsByType: (type) =>
        Object.values(get().results)
          .filter((r) => r.type === type)
          .sort((a, b) => b.timestamp - a.timestamp),
    }),
    { name: "calculator-results" }
  )
);
