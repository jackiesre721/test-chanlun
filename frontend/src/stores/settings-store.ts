import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEFAULT_LAYERS, LAYER_PRESETS, type LayerState, type LayerKey } from "@/constants/layer-presets";

interface SettingsState {
  symbol: string;
  interval: string;
  layers: LayerState;
  compactToolbar: boolean;
  hideSidebar: boolean;
  compactSubplots: boolean;
  activePreset: string;
  dynamicSymbols: string[];
  setSymbol: (s: string) => void;
  setInterval: (i: string) => void;
  toggleLayer: (key: LayerKey) => void;
  applyPreset: (name: string) => void;
  toggleCompactToolbar: () => void;
  toggleHideSidebar: () => void;
  toggleCompactSubplots: () => void;
  setDynamicSymbols: (symbols: string[]) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      symbol: "BTCUSDT",
      interval: "1",
      layers: { ...DEFAULT_LAYERS },
      compactToolbar: false,
      hideSidebar: false,
      compactSubplots: false,
      activePreset: "watch",
      dynamicSymbols: [],

      setSymbol: (s) => set({ symbol: s }),
      setInterval: (i) => set({ interval: i }),
      toggleLayer: (key) =>
        set((s) => ({ layers: { ...s.layers, [key]: !s.layers[key] } })),
      applyPreset: (name) => {
        const preset = LAYER_PRESETS[name];
        if (preset) set({ layers: { ...DEFAULT_LAYERS, ...preset }, activePreset: name });
      },
      toggleCompactToolbar: () => set((s) => ({ compactToolbar: !s.compactToolbar })),
      toggleHideSidebar: () => set((s) => ({ hideSidebar: !s.hideSidebar })),
      toggleCompactSubplots: () => set((s) => ({ compactSubplots: !s.compactSubplots })),
      setDynamicSymbols: (symbols) => set({ dynamicSymbols: symbols }),
    }),
    {
      name: "chanlan_settings",
      partialize: (s) => ({
        layers: s.layers,
        compactToolbar: s.compactToolbar,
        hideSidebar: s.hideSidebar,
        compactSubplots: s.compactSubplots,
      }),
    },
  ),
);
