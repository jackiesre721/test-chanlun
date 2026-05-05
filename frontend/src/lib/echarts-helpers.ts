import type * as echarts from "echarts";

/** Avoid setOption/dispatchAction after dispose (StrictMode remount + deferred timers). */
export function chartIsDisposed(chart: echarts.ECharts): boolean {
  const fn = (chart as unknown as { isDisposed?: () => boolean }).isDisposed;
  return typeof fn === "function" && fn.call(chart);
}

export function updateVisiblePriceScale(chart: echarts.ECharts, klineData: { low: number; high: number }[]) {
  if (chartIsDisposed(chart) || !klineData.length) return;
  const dz = (chart.getOption() as any).dataZoom?.[0] || {};
  const start = Number(dz.start ?? 64);
  const end = Number(dz.end ?? 100);
  const sIdx = Math.max(0, Math.floor((start / 100) * (klineData.length - 1)));
  const eIdx = Math.min(klineData.length - 1, Math.ceil((end / 100) * (klineData.length - 1)));
  const visible = klineData.slice(sIdx, eIdx + 1);
  if (!visible.length) return;
  const minL = visible.reduce((m, k) => Math.min(m, k.low), Infinity);
  const maxH = visible.reduce((m, k) => Math.max(m, k.high), -Infinity);
  const pad = Math.max((maxH - minL) * 0.08, maxH * 0.001);
  chart.setOption({ yAxis: [{ min: minL - pad, max: maxH + pad }, {}, {}] }, { lazyUpdate: true, silent: true });
}

export function navigateToSignal(chart: echarts.ECharts, idx: number, totalLen: number) {
  if (chartIsDisposed(chart)) return;
  const half = 8;
  const s = Math.max(0, ((idx - half) / totalLen) * 100);
  const e = Math.min(100, ((idx + half) / totalLen) * 100);
  chart.dispatchAction({ type: "dataZoom", start: s, end: e });
}
