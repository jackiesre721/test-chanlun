import { levelLabel, higherLabel } from "@/constants/level-maps";

export type LayerKey =
  | "showBis" | "showActiveBi"
  | "showSegments" | "showFractals" | "showSignals"
  | "showDivergences" | "showZhongshu" | "showZhongshuSeg"
  | "showBoll" | "showRsi" | "showFakeBi";

export type LayerState = Record<LayerKey, boolean>;

export const DEFAULT_LAYERS: LayerState = {
  showBis: true, showActiveBi: true,
  showSegments: true, showFractals: false, showSignals: true,
  showDivergences: false, showZhongshu: true, showZhongshuSeg: true,
  showBoll: true, showRsi: true, showFakeBi: false,
};

export const LAYER_PRESETS: Record<string, Partial<LayerState>> = {
  minimal: {
    showBis: true, showActiveBi: true,
    showSegments: true, showFractals: false, showSignals: true,
    showDivergences: false, showZhongshu: true, showZhongshuSeg: true,
    showBoll: false, showRsi: false, showFakeBi: false,
  },
  watch: {
    showBis: true, showActiveBi: true,
    showSegments: true, showFractals: false, showSignals: true,
    showDivergences: false, showZhongshu: true, showZhongshuSeg: true,
    showBoll: true, showRsi: true, showFakeBi: false,
  },
  review: {
    showBis: true, showActiveBi: true,
    showSegments: true, showFractals: true, showSignals: true,
    showDivergences: true, showZhongshu: true, showZhongshuSeg: true,
    showBoll: true, showRsi: true, showFakeBi: false,
  },
};

/** Build dynamic series-name map using actual interval labels (e.g. "5m笔", "30m中枢"). */
export function buildLayerSeriesMap(interval: string): Record<string, string[]> {
  const lv = levelLabel(interval);
  const hi = higherLabel(interval);
  return {
    showBis: [`${lv}笔`],
    showActiveBi: [`${lv}未完成笔`],
    showFractals: ["顶分型", "顶分型(进行中)", "底分型", "底分型(进行中)"],
    showSignals: ["买点", "卖点"],
    showDivergences: ["背驰点"],
    showZhongshu: [`${lv}中枢`],
    showZhongshuSeg: [`${hi}中枢`],
    showSegments: [`${hi}笔`],
    showBoll: ["BOLL"],
    showFakeBi: ["FakeBI"],
    showRsi: ["RSI14"],
  };
}
