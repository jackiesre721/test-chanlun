/**
 * Frontend level-aware mappings — synced with backend HIGHER_INTERVAL.
 */

export const HIGHER_INTERVAL: Record<string, string> = {
  "1": "5",
  "5": "30",
  "15": "60",
  "30": "240",
  "240": "1440",
  "1440": "10080",
  "10080": "43200",
};

export const INTERVAL_LABEL: Record<string, string> = {
  "1": "1m", "5": "5m", "15": "15m", "30": "30m",
  "60": "1h", "240": "4h", "1440": "1d",
  "10080": "1w", "43200": "1M",
};

export function levelLabel(interval: string): string {
  return INTERVAL_LABEL[interval] || interval;
}

export function higherLabel(interval: string): string {
  const hi = HIGHER_INTERVAL[interval];
  return hi ? (INTERVAL_LABEL[hi] || hi) : "上级";
}

/** Buy-point type labels (with direction) */
export const KIND_BUY_NAME: Record<string, string> = {
  first: "一买", second: "二买", second_extend: "二买延伸",
  third: "三买", second_class: "类二买", third_class: "类三买", td9: "TD9",
};

/** Sell-point type labels (with direction) */
export const KIND_SELL_NAME: Record<string, string> = {
  first: "一卖", second: "二卖", second_extend: "二卖延伸",
  third: "三卖", second_class: "类二卖", third_class: "类三卖", td9: "TD9",
};

/** Short chart labels — numbers for on-chart display */
export const KIND_CHART_LABEL: Record<string, string> = {
  first: "1", second: "2", third: "3",
  second_class: "2'", third_class: "3'",
  second_extend: "2+", td9: "T9",
};

/** Format a full signal label like "5m一买" or "30m三卖" */
export function signalLabel(
  level: string | undefined,
  kind: string,
  side: "BUY" | "SELL",
  interval: string,
): string {
  const lv = level === "segment" ? higherLabel(interval) : levelLabel(interval);
  const typeMap = side === "BUY" ? KIND_BUY_NAME : KIND_SELL_NAME;
  const typeName = typeMap[kind] || kind;
  return `${lv}${typeName}`;
}
