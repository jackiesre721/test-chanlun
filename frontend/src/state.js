/** Shared mutable state accessed across modules. */
export const state = {
  chart: null,
  lastResult: null,
  visibleScaleUpdateDepth: 0,
  dataZoomScaleTimer: null,
  glmVerdictAbortController: null,
  backtestTrades: null,  // trade_log from last backtest
};
