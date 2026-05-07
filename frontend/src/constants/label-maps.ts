export const TREND_CODE_LABEL: Record<string, string> = {
  uptrend_zs_stacked: "上涨走势(中枢上移)",
  downtrend_zs_stacked: "下跌走势(中枢下移)",
  consolidation_zs_overlap: "盘整",
  trend_extension_in_zs: "中枢内延伸",
  directional_extension: "方向延伸",
  neutral_single_segment: "中性",
  mixed_counterstack: "段向背离",
  mixed_bidirectional_zs: "双向震荡",
};

export const RECURSION_COMP_LABEL: Record<string, string> = {
  aligned_uptrend: "跨级偏多一致",
  aligned_downtrend: "跨级偏空一致",
  aligned_consolidation: "跨级震荡一致",
  cross_level_divergent: "跨级背离",
  partially_aligned: "部分一致",
  insufficient_higher_data: "上级数据不足",
};

export const KIND_NAME: Record<string, string> = {
  first: "①一类", second: "②二类", second_extend: "②'二类延伸",
  third: "③三类", second_class: "②'类二", third_class: "③'类三", td9: "⑨TD9",
};
