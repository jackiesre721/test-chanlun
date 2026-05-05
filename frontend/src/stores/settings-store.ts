import { create } from "zustand";
import { persist } from "zustand/middleware";
import { DEFAULT_LAYERS, LAYER_PRESETS, type LayerState, type LayerKey } from "@/constants/layer-presets";

/** 侧栏 Tabs：`当下 | 执行与风控 | 研究与回测 | 参考与设置` */
export type SidebarTabKey = "now" | "risk" | "research" | "ref";

interface SettingsState {
  symbol: string;
  interval: string;
  layers: LayerState;
  compactToolbar: boolean;
  hideSidebar: boolean;
  compactSubplots: boolean;
  activePreset: string;
  dynamicSymbols: string[];
  sidebarTab: SidebarTabKey;
  setSidebarTab: (k: SidebarTabKey) => void;
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
      sidebarTab: "now",

      setSidebarTab: (sidebarTab) => set({ sidebarTab }),
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
        sidebarTab: s.sidebarTab,
      }),
    },
  ),
);
