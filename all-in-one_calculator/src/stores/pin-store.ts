"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { PinnedItem } from "@/types/calculator";

const MAX_PINS = 5;

interface PinStore {
  pins: PinnedItem[];
  addPin: (pin: PinnedItem) => boolean;
  removePin: (resultId: string) => void;
  replacePin: (index: number, pin: PinnedItem) => void;
  isPinned: (resultId: string) => boolean;
  isFull: () => boolean;
}

export const usePinStore = create<PinStore>()(
  persist(
    (set, get) => ({
      pins: [],
      addPin: (pin) => {
        if (get().pins.length >= MAX_PINS) return false;
        if (get().isPinned(pin.resultId)) return false;
        set((state) => ({ pins: [...state.pins, pin] }));
        return true;
      },
      removePin: (resultId) =>
        set((state) => ({
          pins: state.pins.filter((p) => p.resultId !== resultId),
        })),
      replacePin: (index, pin) =>
        set((state) => {
          const pins = [...state.pins];
          pins[index] = pin;
          return { pins };
        }),
      isPinned: (resultId) =>
        get().pins.some((p) => p.resultId === resultId),
      isFull: () => get().pins.length >= MAX_PINS,
    }),
    { name: "pinned-items" }
  )
);
