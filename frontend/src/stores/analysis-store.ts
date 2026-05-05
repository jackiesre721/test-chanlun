import { create } from "zustand";
import type { AnalyzeResult } from "@/types/analysis";
import { postAnalyze } from "@/lib/api";

interface AnalysisState {
  lastResult: AnalyzeResult | null;
  analyzing: boolean;
  error: string | null;
  abortController: AbortController | null;
  analyze: (symbol: string, interval: string) => Promise<void>;
  clear: () => void;
}

export const useAnalysisStore = create<AnalysisState>((set, get) => ({
  lastResult: null,
  analyzing: false,
  error: null,
  abortController: null,

  analyze: async (symbol, interval) => {
    const prev = get().abortController;
    prev?.abort();
    const ac = new AbortController();
    set({ analyzing: true, error: null, abortController: ac });
    try {
      const result = await postAnalyze(symbol, interval);
      set({ lastResult: result, analyzing: false, abortController: null });
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      set({ error: (err as Error).message || "分析失败", analyzing: false, abortController: null });
    }
  },

  clear: () => set({ lastResult: null, error: null }),
}));
