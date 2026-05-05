import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { PositionSizeResponse } from "@/types/analysis";
import { postRiskPositionSize } from "@/lib/api";

export type RiskSizingMode = "risk_fraction" | "fixed_quantity";

interface RiskState {
  sizing_mode: RiskSizingMode;
  equity: string;
  fraction: string;
  fixed_quantity: string;
  entry: string;
  stop: string;
  leverage: number;
  result: PositionSizeResponse | null;
  error: string | null;
  computing: boolean;
  setSizingMode: (m: RiskSizingMode) => void;
  setEquity: (v: string) => void;
  setFraction: (v: string) => void;
  setFixedQuantity: (v: string) => void;
  setEntry: (v: string) => void;
  setStop: (v: string) => void;
  setLeverage: (v: number) => void;
  fillFromSignal: (entry: number, stop: number) => void;
  compute: () => Promise<void>;
}

export const useRiskStore = create<RiskState>()(
  persist(
    (set, get) => ({
      sizing_mode: "risk_fraction",
      equity: "",
      fraction: "0.01",
      fixed_quantity: "0.01",
      entry: "",
      stop: "",
      leverage: 5,
      result: null,
      error: null,
      computing: false,

      setSizingMode: (m) => set({ sizing_mode: m }),
      setEquity: (v) => set({ equity: v }),
      setFraction: (v) => set({ fraction: v }),
      setFixedQuantity: (v) => set({ fixed_quantity: v }),
      setEntry: (v) => set({ entry: v }),
      setStop: (v) => set({ stop: v }),
      setLeverage: (v) => set({ leverage: v }),

      fillFromSignal: (entry, stop) => set({ entry: String(entry), stop: String(stop) }),

      compute: async () => {
        const { sizing_mode, equity, fraction, entry, stop, leverage } = get();
        if (sizing_mode === "fixed_quantity") {
          set({ error: null });
          return;
        }
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
      partialize: (s) => ({
        equity: s.equity,
        leverage: s.leverage,
        sizing_mode: s.sizing_mode,
        fixed_quantity: s.fixed_quantity,
        fraction: s.fraction,
      }),
    },
  ),
);
