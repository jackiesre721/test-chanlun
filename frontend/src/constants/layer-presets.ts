export type LayerKey =
  | "showBis" | "showActiveBi" | "showBiPause"
  | "showSegments" | "showFractals" | "showSignals"
  | "showDivergences" | "showZhongshu" | "showZhongshuSeg"
  | "showBoll" | "showRsi" | "showFakeBi"
  | "showBisLv2" | "showZhongshuLv2";

export type LayerState = Record<LayerKey, boolean>;

export const DEFAULT_LAYERS: LayerState = {
  showBis: true, showActiveBi: true, showBiPause: true,
  showSegments: true, showFractals: false, showSignals: true,
  showDivergences: false, showZhongshu: true, showZhongshuSeg: true,
  showBoll: true, showRsi: true, showFakeBi: false,
  showBisLv2: false, showZhongshuLv2: false,
};

export const LAYER_PRESETS: Record<string, Partial<LayerState>> = {
  minimal: {
    showBis: true, showActiveBi: true, showBiPause: false,
    showSegments: true, showFractals: false, showSignals: true,
    showDivergences: false, showZhongshu: true, showZhongshuSeg: true,
    showBoll: false, showRsi: false, showFakeBi: false,
    showBisLv2: false, showZhongshuLv2: false,
  },
  watch: {
    showBis: true, showActiveBi: true, showBiPause: true,
    showSegments: true, showFractals: false, showSignals: true,
    showDivergences: false, showZhongshu: true, showZhongshuSeg: true,
    showBoll: true, showRsi: true, showFakeBi: false,
    showBisLv2: false, showZhongshuLv2: false,
  },
  review: {
    showBis: true, showActiveBi: true, showBiPause: true,
    showSegments: true, showFractals: true, showSignals: true,
    showDivergences: true, showZhongshu: true, showZhongshuSeg: true,
    showBoll: true, showRsi: true, showFakeBi: false,
    showBisLv2: false, showZhongshuLv2: false,
  },
};

export const LAYER_SERIES_MAP: Record<string, string[]> = {
  showBis: ["本级笔"],
  showActiveBi: ["未完成笔"],
  showBiPause: ["笔停顿"],
  showFractals: ["顶分型", "顶分型(进行中)", "底分型", "底分型(进行中)"],
  showSignals: ["买点", "卖点"],
  showDivergences: ["背驰点"],
  showBisLv2: ["上级笔"],
  showZhongshu: ["笔中枢带"],
  showZhongshuSeg: ["线段中枢带"],
  showZhongshuLv2: ["上级中枢"],
  showSegments: ["线段"],
  showBoll: ["BOLL上", "BOLL中", "BOLL下"],
  showFakeBi: ["FakeBI"],
  showRsi: ["RSI14"],
};
