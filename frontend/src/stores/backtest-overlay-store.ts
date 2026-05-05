import { create } from "zustand";
import type { BacktestExecTrade } from "@/types/analysis";

interface BacktestOverlayState {
  symbol: string | null;
  interval: string | null;
  tradeLog: BacktestExecTrade[];
  showOverlay: boolean;
  setFromRun: (symbol: string, interval: string, tradeLog: BacktestExecTrade[]) => void;
  setShowOverlay: (v: boolean) => void;
  clear: () => void;
}

export const useBacktestOverlayStore = create<BacktestOverlayState>((set) => ({
  symbol: null,
  interval: null,
  tradeLog: [],
  showOverlay: false,

  setFromRun: (symbol, interval, tradeLog) =>
    set({
      symbol,
      interval,
      tradeLog,
      showOverlay: tradeLog.length > 0,
    }),

  setShowOverlay: (v) => set({ showOverlay: v }),

  clear: () =>
    set({
      symbol: null,
      interval: null,
      tradeLog: [],
      showOverlay: false,
    }),
}));
