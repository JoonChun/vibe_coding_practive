"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CalculationResult } from "@/types/calculator";

const MAX_HISTORY = 100;

interface HistoryStore {
  history: CalculationResult[];
  addToHistory: (result: CalculationResult) => void;
  removeFromHistory: (id: string) => void;
  clearHistory: () => void;
}

export const useHistoryStore = create<HistoryStore>()(
  persist(
    (set) => ({
      history: [],
      addToHistory: (result) =>
        set((state) => ({
          history: [result, ...state.history].slice(0, MAX_HISTORY),
        })),
      removeFromHistory: (id) =>
        set((state) => ({
          history: state.history.filter((item) => item.id !== id),
        })),
      clearHistory: () => set({ history: [] }),
    }),
    { name: "calculation-history" }
  )
);
