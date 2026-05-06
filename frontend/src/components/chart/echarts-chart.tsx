import { useRef, useEffect, useCallback, useMemo } from "react";
import * as echarts from "echarts";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useBacktestOverlayStore } from "@/stores/backtest-overlay-store";
import { buildChartOption, buildErrorOption } from "./chart-options";
import { chartIsDisposed, updateVisiblePriceScale, navigateToSignal } from "@/lib/echarts-helpers";

export function EChartsChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const zoomTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);
  const { layers, compactSubplots, symbol, interval } = useSettingsStore();
  const btShow = useBacktestOverlayStore((s) => s.showOverlay);
  const btLog = useBacktestOverlayStore((s) => s.tradeLog);
  const btSym = useBacktestOverlayStore((s) => s.symbol);
  const btIv = useBacktestOverlayStore((s) => s.interval);

  // Init chart + click routing (same lifecycle — StrictMode-safe)
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current, undefined, { renderer: "canvas" });
    chartRef.current = chart;

    const onChartClick = (params: { data?: unknown }) => {
      const d = params.data as { chanSignalKind?: string; chanSignalIdx?: number } | undefined;
      if (d?.chanSignalKind === "trade" || d?.chanSignalKind === "divergence") {
        window.dispatchEvent(
          new CustomEvent("chanlan:chart-click-signal", { detail: { idx: d.chanSignalIdx } }),
        );
      }
    };
    chart.on("click", onChartClick);

    const onResize = () => {
      if (!chartIsDisposed(chart)) chart.resize();
    };
    window.addEventListener("resize", onResize);

    const ro = new ResizeObserver(onResize);
    ro.observe(containerRef.current);

    return () => {
      chart.off("click", onChartClick);
      window.removeEventListener("resize", onResize);
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  // DataZoom handler for autoscale
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const handler = () => {
      if (zoomTimerRef.current) clearTimeout(zoomTimerRef.current);
      zoomTimerRef.current = setTimeout(() => {
        zoomTimerRef.current = null;
        const c = chartRef.current;
        const kd = lastResult?.kline_data;
        if (!c || chartIsDisposed(c) || !kd?.length) return;
        updateVisiblePriceScale(c, kd);
      }, 32);
    };
    chart.on("dataZoom", handler);
    return () => {
      chart.off("dataZoom", handler);
      if (zoomTimerRef.current) clearTimeout(zoomTimerRef.current);
    };
  }, [lastResult]);

  // Update chart when result/settings change
  const option = useMemo(() => {
    if (error) return buildErrorOption(error);
    if (!lastResult) return null;
    return buildChartOption(lastResult, {
      layers,
      compactSubplots,
      backtestOverlay: {
        show: btShow,
        trades: btLog,
        btSymbol: btSym ?? "",
        btInterval: btIv ?? "",
        chartSymbol: symbol,
        chartInterval: interval,
      },
    }, interval);
  }, [
    lastResult,
    layers,
    compactSubplots,
    error,
    btShow,
    btLog,
    btSym,
    btIv,
    symbol,
    interval,
  ]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || chartIsDisposed(chart) || !option) return;
    chart.setOption(option, { notMerge: true, lazyUpdate: true });
    if (lastResult?.kline_data) updateVisiblePriceScale(chart, lastResult.kline_data);
  }, [option, lastResult]);

  // Expose navigateToSignal via store or callback
  const onSignalNavigate = useCallback((idx: number) => {
    const chart = chartRef.current;
    const len = lastResult?.kline_data?.length;
    if (!chart || chartIsDisposed(chart) || !len) return;
    navigateToSignal(chart, idx, len);
  }, [lastResult]);

  // Store the navigate function for sidebar signal cards to use
  useEffect(() => {
    (window as any).__chanlan_navigateToSignal = onSignalNavigate;
    return () => { delete (window as any).__chanlan_navigateToSignal; };
  }, [onSignalNavigate]);

  return <div ref={containerRef} className="w-full h-full" />;
}
