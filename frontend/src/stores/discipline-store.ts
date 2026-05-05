import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AnalyzeResult } from "@/types/analysis";

interface RuleSnapshot {
  rules_version: string;
  segment_engine: string;
  timestamp: number;
}

interface DisciplineState {
  consecutiveLosses: number;
  threshold: number;
  hypothesisNotes: string;
  ruleSnapshot: RuleSnapshot | null;
  incrementLoss: () => void;
  resetLosses: () => void;
  setThreshold: (t: number) => void;
  setHypothesisNotes: (n: string) => void;
  updateRuleSnap: (result: AnalyzeResult) => void;
  clearRuleSnap: () => void;
}

export const useDisciplineStore = create<DisciplineState>()(
  persist(
    (set) => ({
      consecutiveLosses: 0,
      threshold: 5,
      hypothesisNotes: "",
      ruleSnapshot: null,

      incrementLoss: () => set((s) => ({ consecutiveLosses: s.consecutiveLosses + 1 })),
      resetLosses: () => set({ consecutiveLosses: 0 }),
      setThreshold: (t) => set({ threshold: t }),
      setHypothesisNotes: (n) => set({ hypothesisNotes: n }),
      updateRuleSnap: (result) =>
        set({
          ruleSnapshot: {
            rules_version: result.rules_version || result.meta?.rules_version || "unknown",
            segment_engine: result.segment_engine || result.meta?.segment_engine || "unknown",
            timestamp: Date.now(),
          },
        }),
      clearRuleSnap: () => set({ ruleSnapshot: null }),
    }),
    {
      name: "chanlan_discipline",
      partialize: (s) => ({
        consecutiveLosses: s.consecutiveLosses,
        threshold: s.threshold,
        hypothesisNotes: s.hypothesisNotes,
      }),
    },
  ),
);
