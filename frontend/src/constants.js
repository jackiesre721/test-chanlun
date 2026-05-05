/** Main-chart element color palette — each structural layer uses a distinct hue. */
export const CHART_PALETTE = {
  kUp: "#26a69a",
  kDown: "#ef5350",
  priceLine: "#ffe082",
  bi: "rgba(255,255,255,0.78)",
  activeBi: "#00bcd4",
  segment: "#42a5f5",
  higherBi: "#42a5f5",
  fractalTop: "#ba68c8",
  fractalTopTent: "rgba(186, 104, 200, 0.65)",
  fractalTopBorder: "#e1bee7",
  fractalBottom: "#66bb6a",
  fractalBottomTent: "rgba(102, 187, 106, 0.55)",
  fractalBottomBorder: "#c8e6c9",
  signalBuy: "#00e676",
  signalSell: "#ff1744",
  signalBuySegment: "#29b6f6",
  signalSellSegment: "#ff6e40",
  divergenceDown: "#00bfa5",
  divergenceUp: "#f06292",
  divergenceLabel: "#fff9c4",
  pause: "#ffee58",
  pauseBorder: "#5d4037",
  pivotBi: { fill: "rgba(255,255,255,0.22)", border: "rgba(255,255,255,0.70)" },
  pivotSegment: { fill: "rgba(66,165,245,0.28)", border: "rgba(66,165,245,0.75)" },
  pivotHigher: { fill: "rgba(236, 64, 122, 0.30)", border: "rgba(255, 205, 210, 0.85)" },
  macdPos: "rgba(38, 166, 154, 0.78)",
  macdNeg: "rgba(239, 83, 80, 0.78)",
  dif: "#4fc3f7",
  dea: "#ffb74d",
  zeroLine: "rgba(255,255,255,.38)",
  linesFormText: "#ffe082",
  bollUpper: "rgba(255,183,77,.72)",
  bollMid: "rgba(255,183,77,.42)",
  bollLower: "rgba(255,183,77,.72)",
  rsiLine: "#ce93d8",
  fakeBi: "rgba(189,189,189,.45)"
};

/** Matches backend AnalyzeRequest.limit. */
export const ANALYZE_LIMIT = 2500;

/** Layer toggle presets: each key maps checkbox IDs to checked state. */
export const LAYER_PRESETS = {
  minimal: {
    showBis: true, showActiveBi: false, showBiPause: false,
    showSegments: true, showFractals: false, showSignals: true,
    showDivergences: true, showZhongshu: true, showZhongshuSeg: true,
    showBoll: false, showMacd: true,
    showBisLv2: false, showZhongshuLv2: false,
  },
  watch: {
    showBis: true, showActiveBi: true, showBiPause: true,
    showSegments: true, showFractals: false, showSignals: true,
    showDivergences: false, showZhongshu: true, showZhongshuSeg: true,
    showBoll: true, showMacd: true,
    showBisLv2: false, showZhongshuLv2: false,
  },
  review: {
    showBis: true, showActiveBi: true, showBiPause: true,
    showSegments: true, showFractals: true, showSignals: true,
    showDivergences: true, showZhongshu: true, showZhongshuSeg: true,
    showBoll: true, showMacd: true,
    showBisLv2: false, showZhongshuLv2: false,
  },
};

export const TREND_CODE_LABEL = {
  uptrend_zs_stacked: "上涨走势(中枢上移)",
  downtrend_zs_stacked: "下跌走势(中枢下移)",
  consolidation_zs_overlap: "盘整",
  trend_extension_in_zs: "中枢内延伸",
  directional_extension: "方向延伸",
  neutral_single_segment: "中性",
  mixed_counterstack: "段向背离",
  mixed_bidirectional_zs: "双向震荡"
};

export const RECURSION_COMP_LABEL = {
  aligned_uptrend: "跨级偏多一致",
  aligned_downtrend: "跨级偏空一致",
  aligned_consolidation: "跨级震荡一致",
  cross_level_divergent: "跨级背离",
  partially_aligned: "部分一致",
  insufficient_higher_data: "上级数据不足"
};

export const KIND_NAME = {
  first: "一类", second: "二类", second_extend: "二类延伸",
  third: "三类", second_class: "类二", third_class: "类三", td9: "TD9"
};

export const SIGNAL_LEVEL_LABEL = {
  bi: "笔级别", segment: "线段级别",
};

/** Maps current interval code to the higher-level label for segment ≈ higher stroke. */
export const HIGHER_INTERVAL_LABEL = {
  "1": "5m",
  "5": "30m",
  "15": "1h",
  "30": "4h",
  "60": "4h",
  "240": "1d",
  "1440": "1w",
  "10080": "1M",
  "43200": "",
};

/** Maps checkbox IDs to the ECharts series names they control. */
export const LAYER_SERIES_MAP = {
  showBis: ["本级笔"],
  showActiveBi: ["未完成笔"],
  showBiPause: ["笔停顿"],
  showFractals: ["顶分型", "顶分型(进行中)", "底分型", "底分型(进行中)"],
  showSignals: ["笔级买点", "笔级卖点", "段级买点", "段级卖点", "过滤买点", "过滤卖点"],
  showDivergences: ["背驰点"],
  showBisLv2: ["上级笔"],
  showZhongshu: ["笔中枢带"],
  showZhongshuSeg: ["线段中枢带"],
  showZhongshuLv2: ["上级中枢"],
  showSegments: ["线段"],
  showBoll: ["BOLL上", "BOLL中", "BOLL下"],
  showMacd: ["MACD", "DIF", "DEA"],
};
