import { state } from "./state.js";

function currentVisibleRange(length) {
  const dataZoom = state.chart.getOption().dataZoom?.[0] || {};
  const start = Number(dataZoom.start ?? 64);
  const end = Number(dataZoom.end ?? 100);
  return {
    startIdx: Math.max(0, Math.floor((start / 100) * (length - 1))),
    endIdx: Math.min(length - 1, Math.ceil((end / 100) * (length - 1)))
  };
}

export function updateVisiblePriceScale() {
  if (!state.lastResult || !state.lastResult.kline_data.length) return;
  if (state.visibleScaleUpdateDepth > 0) return;
  state.visibleScaleUpdateDepth++;
  try {
    const range = currentVisibleRange(state.lastResult.kline_data.length);
    const visibleCandles = state.lastResult.kline_data.slice(range.startIdx, range.endIdx + 1);
    if (!visibleCandles.length) return;
    const minLow = visibleCandles.reduce((m, k) => Math.min(m, k.low), Infinity);
    const maxHigh = visibleCandles.reduce((m, k) => Math.max(m, k.high), -Infinity);
    const padding = Math.max((maxHigh - minLow) * 0.08, maxHigh * 0.001);
    state.chart.setOption(
      {
        yAxis: [
          { min: minLow - padding, max: maxHigh + padding },
          {},
          {}
        ]
      },
      { lazyUpdate: true, silent: true }
    );
  } finally {
    state.visibleScaleUpdateDepth--;
  }
}

export function scheduleVisiblePriceScaleFromDataZoom() {
  if (state.dataZoomScaleTimer) clearTimeout(state.dataZoomScaleTimer);
  state.dataZoomScaleTimer = setTimeout(() => {
    state.dataZoomScaleTimer = null;
    updateVisiblePriceScale();
  }, 32);
}
