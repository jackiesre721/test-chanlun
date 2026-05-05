import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { PositionSizeResponse } from "@/types/analysis";
import { postRiskPositionSize } from "@/lib/api";

interface RiskState {
  equity: string;
  fraction: string;
  entry: string;
  stop: string;
  leverage: number;
  result: PositionSizeResponse | null;
  error: string | null;
  computing: boolean;
  setEquity: (v: string) => void;
  setFraction: (v: string) => void;
  setEntry: (v: string) => void;
  setStop: (v: string) => void;
  setLeverage: (v: number) => void;
  fillFromSignal: (entry: number, stop: number) => void;
  compute: () => Promise<void>;
}

export const useRiskStore = create<RiskState>()(
  persist(
    (set, get) => ({
      equity: "",
      fraction: "0.01",
      entry: "",
      stop: "",
      leverage: 5,
      result: null,
      error: null,
      computing: false,

      setEquity: (v) => set({ equity: v }),
      setFraction: (v) => set({ fraction: v }),
      setEntry: (v) => set({ entry: v }),
      setStop: (v) => set({ stop: v }),
      setLeverage: (v) => set({ leverage: v }),

      fillFromSignal: (entry, stop) => set({ entry: String(entry), stop: String(stop) }),

      compute: async () => {
        const { equity, fraction, entry, stop, leverage } = get();
        const eq = Number(equity);
        const fr = Number(fraction);
        const en = Number(entry);
        const st = Number(stop);
        if (!eq || !fr || !en || !st || en === st) {
          set({ error: "请填写权益、风险比例、入场价、止损价" });
          return;
        }
        set({ computing: true, error: null });
        try {
          const result = await postRiskPositionSize({
            equity: eq,
            risk_fraction: fr,
            entry_price: en,
            stop_price: st,
            leverage,
          });
          set({ result, computing: false });
        } catch (e: unknown) {
          set({ error: (e as Error).message, computing: false });
        }
      },
    }),
    {
      name: "chanlan_risk",
      partialize: (s) => ({ equity: s.equity, leverage: s.leverage }),
    },
  ),
);
