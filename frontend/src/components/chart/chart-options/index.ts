import type { AnalyzeResult, Stroke, Fractal, Divergence, Pivot, KlineBar, BacktestExecTrade } from "@/types/analysis";
import { CHART_PALETTE, ANALYZE_LIMIT } from "@/constants/chart-palette";
import { LAYER_SERIES_MAP, type LayerState } from "@/constants/layer-presets";
import { fmtOpenTime } from "@/lib/format";

export interface ChartSettings {
  layers: LayerState;
  compactSubplots: boolean;
  /** 主图叠加最近一次演示回测成交（品种+周期须与当前图表一致） */
  backtestOverlay?: {
    show: boolean;
    trades: BacktestExecTrade[];
    btSymbol: string;
    btInterval: string;
    chartSymbol: string;
    chartInterval: string;
  };
}

// ── helpers ──

function fractalX(f: Fractal): number {
  const n = f.norm_idx;
  return n != null && Number.isFinite(Number(n)) ? Number(n) : Number(f.idx);
}

function strokeLine(name: string, strokes: Stroke[], len: number, color: string, width: number, dashed = false) {
  const data = Array(len).fill(null) as (number | null)[];
  for (const s of strokes) {
    if (s.start_idx >= 0 && s.start_idx < len) data[s.start_idx] = s.start_price;
    if (s.end_idx >= 0 && s.end_idx < len) data[s.end_idx] = s.end_price;
  }
  const lineStyle: Record<string, unknown> = { color, width };
  if (dashed) lineStyle.type = "dashed";
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 5,
    data, connectNulls: true, symbol: "circle", symbolSize: 5,
    lineStyle, itemStyle: { color }, emphasis: { disabled: true },
  };
}

function segmentPolyline(name: string, segments: AnalyzeResult["segments"], bis: Stroke[], len: number, color: string, width: number) {
  if (!segments?.length || !bis.length || !len) return null;
  const data = Array(len).fill(null) as (number | null)[];
  const fillSpan = (st: Stroke) => {
    if (!st) return;
    const ns = st.norm_start_idx != null ? Number(st.norm_start_idx) : Number(st.start_idx);
    const ne = st.norm_end_idx != null ? Number(st.norm_end_idx) : Number(st.end_idx);
    const a = Math.min(ns, ne), z = Math.max(ns, ne);
    let pa = st.start_price, pz = st.end_price;
    if (ns !== a) { pa = st.end_price; pz = st.start_price; }
    const span = z - a;
    if (span <= 0) { if (a >= 0 && a < len) data[a] = pa; return; }
    for (let k = a; k <= z && k < len; k++) data[k] = pa + (pz - pa) * ((k - a) / span);
  };
  for (const seg of segments) {
    const lo = Math.max(0, Math.floor(Number(seg.start_idx)));
    const hi = Math.min(bis.length - 1, Math.floor(Number(seg.end_idx)));
    for (let i = lo; i <= hi; i++) fillSpan(bis[i]);
  }
  if (!data.some(v => v != null)) return null;
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 8,
    data, connectNulls: false, showSymbol: false, symbol: "none",
    lineStyle: { color, width, cap: "round", join: "round", shadowBlur: 10, shadowColor: "rgba(255,167,38,0.45)", shadowOffsetY: 0 },
    itemStyle: { color }, emphasis: { disabled: true },
  };
}

function activeBiLine(stroke: Stroke, len: number) {
  const data = Array(len).fill(null) as (number | null)[];
  if (stroke.start_idx >= 0 && stroke.start_idx < len) data[stroke.start_idx] = stroke.start_price;
  if (stroke.end_idx >= 0 && stroke.end_idx < len) data[stroke.end_idx] = stroke.end_price;
  return {
    name: "未完成笔", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 5,
    data, connectNulls: true, symbol: "circle", symbolSize: 6,
    lineStyle: { color: CHART_PALETTE.activeBi, width: 2, type: "dashed" },
    itemStyle: { color: CHART_PALETTE.activeBi }, emphasis: { disabled: true },
  };
}

function fractalScatter(fractals: Fractal[]) {
  const okTop = (f: Fractal) => f.type === "TOP" && f.confirmed !== false;
  const tentTop = (f: Fractal) => f.type === "TOP" && f.confirmed === false;
  const okBot = (f: Fractal) => f.type === "BOTTOM" && f.confirmed !== false;
  const tentBot = (f: Fractal) => f.type === "BOTTOM" && f.confirmed === false;
  const withStr = (f: Fractal) => {
    const v = [fractalX(f), f.price];
    const s = f.strength_hint != null ? Math.round(Number(f.strength_hint) * 100) : null;
    return s != null ? { value: v, fractalStrength: s } : { value: v };
  };
  return [
    { name: "顶分型", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 6, symbol: "triangle", symbolSize: 10, symbolRotate: 180,
      itemStyle: { color: CHART_PALETTE.fractalTop, borderColor: CHART_PALETTE.fractalTopBorder, borderWidth: 1 },
      label: { show: true, position: "top", distance: 2, fontSize: 9, color: "#e1bee7", formatter: (p: any) => p.data.fractalStrength != null ? p.data.fractalStrength + "%" : "" },
      data: fractals.filter(okTop).map(withStr) },
    { name: "顶分型(进行中)", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 5, symbol: "triangle", symbolSize: 7, symbolRotate: 180,
      itemStyle: { color: CHART_PALETTE.fractalTopTent, borderColor: CHART_PALETTE.fractalTopBorder, borderWidth: 1 },
      label: { show: true, position: "top", fontSize: 8, color: "#e1bee7", formatter: "?" },
      data: fractals.filter(tentTop).map(f => [fractalX(f), f.price]) },
    { name: "底分型", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 6, symbol: "triangle", symbolSize: 10,
      itemStyle: { color: CHART_PALETTE.fractalBottom, borderColor: CHART_PALETTE.fractalBottomBorder, borderWidth: 1 },
      label: { show: true, position: "bottom", distance: 2, fontSize: 9, color: "#c8e6c9", formatter: (p: any) => p.data.fractalStrength != null ? p.data.fractalStrength + "%" : "" },
      data: fractals.filter(okBot).map(withStr) },
    { name: "底分型(进行中)", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 5, symbol: "triangle", symbolSize: 7,
      itemStyle: { color: CHART_PALETTE.fractalBottomTent, borderColor: CHART_PALETTE.fractalBottomBorder, borderWidth: 1 },
      label: { show: true, position: "bottom", fontSize: 8, color: "#c8e6c9", formatter: "?" },
      data: fractals.filter(tentBot).map(f => [fractalX(f), f.price]) },
  ];
}

function pivotBand(name: string, pivots: Pivot[], pal: { fill: string; border: string }) {
  const segBand = name.includes("线段");
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 1, data: [], silent: true, tooltip: { show: false },
    markArea: {
      silent: true,
      itemStyle: { color: pal.fill, borderColor: pal.border, borderWidth: 1.25, borderType: segBand ? "dashed" : "solid", shadowBlur: 8, shadowColor: "rgba(0,0,0,0.45)" },
      data: pivots.map(p => [{ xAxis: p.start_idx, yAxis: p.zd }, { xAxis: p.end_idx, yAxis: p.zg }]),
    },
  };
}

function divergenceScatter(divergences: Divergence[]) {
  return {
    name: "背驰点", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 12, symbol: "diamond", symbolSize: 13,
    itemStyle: { borderColor: "#eceff1", borderWidth: 1.5 },
    label: { show: true, position: "top", distance: 3, fontSize: 10, fontWeight: 700, color: CHART_PALETTE.divergenceLabel, textBorderColor: "#263238", textBorderWidth: 2,
      formatter(p: any) { const d = p.data?.dv; return d?.structure_kind === "trend" ? "趋势背驰" : "盘整背驰"; } },
    data: divergences.map(d => ({
      value: [d.idx, d.price], dv: d, chanSignalKind: "divergence", chanSignalIdx: d.idx,
      itemStyle: { color: d.direction === "DOWN" ? CHART_PALETTE.divergenceDown : CHART_PALETTE.divergenceUp },
    })),
    emphasis: { scale: 1.35 },
  };
}

function biPauseScatter(bis: Stroke[]) {
  const pts = bis.filter(b => b.pause_after_end === true).map(b => {
    const x = b.norm_end_idx != null ? b.norm_end_idx : b.end_idx;
    return { value: [x, b.end_price] };
  });
  if (!pts.length) return null;
  return {
    name: "笔停顿", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 11, symbol: "pin", symbolSize: 11,
    itemStyle: { color: CHART_PALETTE.pause, borderColor: CHART_PALETTE.pauseBorder, borderWidth: 1 },
    label: { show: true, position: "bottom", distance: 2, fontSize: 9, color: "#fffde7", formatter: "停顿" },
    data: pts,
  };
}

function signalScatter(name: string, signals: AnalyzeResult["buy_signals"], color: string, sym: string) {
  return {
    name, type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 13, symbol: sym, symbolSize: 17,
    itemStyle: { color, borderColor: "#263238", borderWidth: 1.5 },
    data: signals.map(s => ({
      value: [s.idx, s.price], chanSignalKind: "trade", chanSignalIdx: s.idx, chanSignalSide: s.side,
      itemStyle: { color, borderColor: "#263238", borderWidth: 1.5 },
    })),
  };
}

function resolveBacktestXIndex(klines: KlineBar[], t: BacktestExecTrade): number {
  const len = klines.length;
  const bi = Number(t.bar_idx);
  if (bi >= 0 && bi < len) {
    const k = klines[bi];
    const tt = t.time;
    if (!tt) return bi;
    if (String(k.time) === tt) return bi;
    if (k.open_time != null && fmtOpenTime(k.open_time) === tt) return bi;
  }
  if (t.time) {
    const byTime = klines.findIndex((k) => String(k.time) === t.time);
    if (byTime >= 0) return byTime;
    const byFmt = klines.findIndex(
      (k) => k.open_time != null && fmtOpenTime(k.open_time) === t.time,
    );
    if (byFmt >= 0) return byFmt;
  }
  return bi >= 0 && bi < len ? bi : -1;
}

function buildBacktestOverlaySeries(trades: BacktestExecTrade[], klines: KlineBar[]) {
  const buys: { value: [number, number] }[] = [];
  const sells: { value: [number, number] }[] = [];
  for (const t of trades) {
    const xi = resolveBacktestXIndex(klines, t);
    if (xi < 0 || !Number.isFinite(t.price)) continue;
    const item = { value: [xi, t.price] as [number, number] };
    if (t.action === "BUY") buys.push(item);
    else sells.push(item);
  }
  return [
    {
      name: "回测·买",
      type: "scatter",
      xAxisIndex: 0,
      yAxisIndex: 0,
      z: 14,
      symbol: "triangle",
      symbolSize: 12,
      itemStyle: { color: "#69f0ae", borderColor: "#1b5e20", borderWidth: 1 },
      data: buys,
    },
    {
      name: "回测·卖",
      type: "scatter",
      xAxisIndex: 0,
      yAxisIndex: 0,
      z: 14,
      symbol: "pin",
      symbolRotate: 180,
      symbolSize: 12,
      itemStyle: { color: "#ff8a80", borderColor: "#b71c1c", borderWidth: 1 },
      data: sells,
    },
  ];
}

function linesFormGraphic(result: AnalyzeResult) {
  const lf = result.lines_form;
  if (!lf?.primary) return [];
  const det = lf.detail_zh ? String(lf.detail_zh) : "";
  const detShort = det.length > 52 ? det.slice(0, 52) + "…" : det;
  const eng = result.segment_engine === "strict67" ? "67课特征序列" : "legacy 三笔重叠";
  const text = `走势形态：${lf.primary}${detShort ? " ｜ " + detShort : ""} ｜ ${eng}`;
  return [{ type: "text", left: 52, top: 40, z: 80, style: { text, fill: CHART_PALETTE.linesFormText, font: "700 11px system-ui, -apple-system, sans-serif", width: Math.min(typeof window !== "undefined" ? window.innerWidth * 0.55 : 720, 720), overflow: "truncate" } }];
}

// ── main builder ──

export function buildChartOption(result: AnalyzeResult, settings: ChartSettings) {
  const times = result.kline_data.map(k => k.time);
  const len = times.length;
  const candles = result.kline_data.map(k => [k.open, k.close, k.low, k.high]);
  const macdBars = result.macd_data.map(m => m.hist);
  const dif = result.macd_data.map(m => m.dif);
  const dea = result.macd_data.map(m => m.dea);

  const series: any[] = [
    {
      name: "K线", type: "candlestick", data: candles, xAxisIndex: 0, yAxisIndex: 0, z: 3,
      itemStyle: { color: CHART_PALETTE.kUp, color0: CHART_PALETTE.kDown, borderColor: CHART_PALETTE.kUp, borderColor0: CHART_PALETTE.kDown },
      markLine: { symbol: "none", data: [{ yAxis: result.current_price, label: { formatter: result.current_price.toFixed(2) } }], lineStyle: { color: CHART_PALETTE.priceLine, type: "dashed" } },
    },
  ];

  const zhAll = result.zhongshus || [];
  const biPivots = zhAll.filter(p => p.level === "bi");
  const segPivots = zhAll.filter(p => p.level === "segment");

  series.push(strokeLine("本级笔", result.bis, len, CHART_PALETTE.bi, 2));
  if (result.active_bi) series.push(activeBiLine(result.active_bi, len));
  const pauseS = biPauseScatter(result.bis);
  if (pauseS) series.push(pauseS);
  series.push(...fractalScatter(result.fractals));
  series.push(signalScatter("买点", result.buy_signals || [], CHART_PALETTE.signalBuy, "triangle"));
  series.push(signalScatter("卖点", result.sell_signals || [], CHART_PALETTE.signalSell, "pin"));
  if (result.divergences?.length) series.push(divergenceScatter(result.divergences));
  series.push(strokeLine("上级笔", result.bis_lv2 || [], len, CHART_PALETTE.higherBi, 2, true));
  if (biPivots.length) series.push(pivotBand("笔中枢带", biPivots, CHART_PALETTE.pivotBi));
  if (segPivots.length) series.push(pivotBand("线段中枢带", segPivots, CHART_PALETTE.pivotSegment));
  if (result.zhongshus_lv2?.length) series.push(pivotBand("上级中枢", result.zhongshus_lv2, CHART_PALETTE.pivotHigher));
  const sp = segmentPolyline("线段", result.segments, result.bis, len, CHART_PALETTE.segment, 4);
  if (sp) series.push(sp);

  const boll = result.bollinger || [];
  if (boll.length === len) {
    series.push({ name: "BOLL上", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 4, data: boll.map(b => b.upper), symbol: "none", lineStyle: { width: 1, color: CHART_PALETTE.bollUpper } });
    series.push({ name: "BOLL中", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 4, data: boll.map(b => b.mid), symbol: "none", lineStyle: { width: 1, type: "dotted", color: CHART_PALETTE.bollMid } });
    series.push({ name: "BOLL下", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 4, data: boll.map(b => b.lower), symbol: "none", lineStyle: { width: 1, color: CHART_PALETTE.bollLower } });
  }
  if (result.fake_bis?.length) {
    const data = Array(len).fill(null) as (number | null)[];
    for (const fb of result.fake_bis) {
      if (fb.start_idx >= 0 && fb.start_idx < len) data[fb.start_idx] = fb.start_price;
      if (fb.end_idx >= 0 && fb.end_idx < len) data[fb.end_idx] = fb.end_price;
    }
    series.push({ name: "FakeBI", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 2, data, connectNulls: true, symbol: "none", lineStyle: { color: CHART_PALETTE.fakeBi, width: 1, type: "dashed" } });
  }

  // MACD sub-chart
  series.push({ name: "MACD", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: macdBars, itemStyle: { color: (p: any) => p.data >= 0 ? CHART_PALETTE.macdPos : CHART_PALETTE.macdNeg } });
  series.push({ name: "DIF", type: "line", xAxisIndex: 1, yAxisIndex: 1, data: dif, symbol: "none", lineStyle: { color: CHART_PALETTE.dif, width: 1.5 },
    markLine: { silent: true, symbol: "none", lineStyle: { color: CHART_PALETTE.zeroLine, width: 1, type: "dashed" }, label: { show: true, formatter: "0", color: "rgba(209,212,220,.5)", fontSize: 9 }, data: [{ yAxis: 0 }] } });
  series.push({ name: "DEA", type: "line", xAxisIndex: 1, yAxisIndex: 1, data: dea, symbol: "none", lineStyle: { color: CHART_PALETTE.dea, width: 1.5 } });

  // RSI sub-chart
  const rsiA = result.rsi14 || [];
  if (rsiA.length === len) {
    series.push({ name: "RSI14", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: rsiA, symbol: "none", lineStyle: { color: CHART_PALETTE.rsiLine, width: 1.2 },
      markLine: { silent: true, symbol: "none", lineStyle: { color: "rgba(255,255,255,.2)", type: "dashed" }, data: [{ yAxis: 70 }, { yAxis: 30 }] } });
  }

  // Legend visibility from layer settings
  const legendSelected: Record<string, boolean> = {};
  for (const [key, names] of Object.entries(LAYER_SERIES_MAP)) {
    const checked = settings.layers[key as keyof typeof settings.layers] ?? true;
    for (const n of names) legendSelected[n] = checked;
  }

  const bo = settings.backtestOverlay;
  const symEq =
    bo != null &&
    bo.btSymbol.trim().toUpperCase() === bo.chartSymbol.trim().toUpperCase();
  const overlayAlign =
    bo?.show &&
    bo.trades.length > 0 &&
    symEq &&
    String(bo.btInterval) === String(bo.chartInterval);
  if (overlayAlign) {
    series.push(...buildBacktestOverlaySeries(bo.trades, result.kline_data));
    legendSelected["回测·买"] = true;
    legendSelected["回测·卖"] = true;
  }

  const subC = settings.compactSubplots;
  const grids = subC
    ? [{ left: 48, right: 68, top: 28, height: "58%" }, { left: 48, right: 68, top: "67%", height: "9%" }, { left: 48, right: 68, top: "78%", height: "9%" }]
    : [{ left: 50, right: 70, top: 46, height: "46%" }, { left: 50, right: 70, top: "60%", height: "10%" }, { left: 50, right: 70, top: "72%", height: "10%" }];

  return {
    backgroundColor: "#12161f",
    animation: false,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross", crossStyle: { color: "rgba(255,255,255,.22)", width: 1 }, label: { backgroundColor: "rgba(18,22,31,.92)", borderColor: "rgba(255,255,255,.08)", color: "#e8eaf0" } },
      backgroundColor: "rgba(14,17,24,.94)", borderColor: "rgba(255,255,255,.09)", borderWidth: 1, padding: [10, 13],
      extraCssText: "border-radius:8px;box-shadow:0 12px 40px rgba(0,0,0,.45);",
      textStyle: { color: "#e8eaf0", fontSize: 11, fontFamily: "Inter, Noto Sans SC, sans-serif" },
      formatter(params: any[]) {
        if (!params?.length) return "";
        const idx = params[0].dataIndex;
        const k = result.kline_data?.[idx];
        let head = params[0].axisValueLabel || params[0].name || "";
        if (k?.open_time != null) head = `<div style="font-weight:800;margin-bottom:4px;">${fmtOpenTime(k.open_time)}</div><div style="opacity:.82;font-size:11px;">轴标 ${params[0].axisValueLabel || ""}</div>`;
        const lines = [head];
        for (const q of params) {
          if (q.seriesType === "candlestick" && q.data?.length >= 4) {
            const [o, c, l, h] = q.data;
            lines.push(`${q.seriesName} O=${o} H=${h} L=${l} C=${c}`);
          } else if (q.seriesType === "scatter") {
            const d = q.data;
            if (d?.dv) { lines.push(`${q.seriesName}：${d.dv.description || ""}`); }
            else if (d?.chanSignalKind === "trade") { lines.push(`${q.seriesName}：索引 ${d.chanSignalIdx}（点击联动侧栏）`); }
            else if (d?.fractalStrength != null) { lines.push(`${q.seriesName} 力度≈${d.fractalStrength}%`); }
          } else if (q.value != null) {
            const v = Array.isArray(q.value) ? q.value.map((x: any) => typeof x === "number" ? x.toFixed(4) : x).join(", ") : String(q.value);
            lines.push(`${q.seriesName} ${v}`);
          }
        }
        return lines.join("<br/>");
      },
    },
    legend: {
      type: "scroll", top: subC ? 4 : 10, itemGap: 12, icon: "roundRect", itemWidth: 10, itemHeight: 10,
      selected: legendSelected,
      pageIconColor: "rgba(228,232,240,.45)", pageTextStyle: { color: "rgba(228,232,240,.45)", fontSize: 10 },
      textStyle: { color: "rgba(228,232,240,.72)", fontSize: 11, fontFamily: "Inter, Noto Sans SC, sans-serif" },
    },
    graphic: linesFormGraphic(result),
    axisPointer: { link: [{ xAxisIndex: [0, 1, 2] }] },
    grid: grids,
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1, 2], start: 64, end: 100, filterMode: "none" },
      { type: "slider", xAxisIndex: [0, 1, 2], start: 64, end: 100, bottom: 10, height: 20, filterMode: "none",
        backgroundColor: "rgba(0,0,0,.28)", borderColor: "rgba(255,255,255,.06)",
        fillerColor: "rgba(79,139,255,.16)", handleStyle: { color: "#4580ff", borderColor: "rgba(255,255,255,.2)" },
        textStyle: { color: "rgba(228,232,240,.42)", fontSize: 10 }, moveHandleStyle: { color: "rgba(79,139,255,.35)" } },
    ],
    xAxis: [
      { type: "category", data: times, axisLine: { lineStyle: { color: "rgba(255,255,255,.08)" } }, axisTick: { show: false }, axisLabel: { color: "rgba(209,214,224,.52)", fontSize: 10 } },
      { type: "category", data: times, gridIndex: 1, axisLine: { lineStyle: { color: "rgba(255,255,255,.06)" } }, axisTick: { show: false }, axisLabel: { color: "rgba(209,214,224,.42)", fontSize: 10 } },
      { type: "category", data: times, gridIndex: 2, axisLine: { lineStyle: { color: "rgba(255,255,255,.06)" } }, axisTick: { show: false }, axisLabel: { color: "rgba(209,214,224,.38)", fontSize: 10 } },
    ],
    yAxis: [
      { scale: true, position: "right", splitLine: { lineStyle: { color: "rgba(255,255,255,.045)", type: "dashed" } }, axisLabel: { color: "rgba(209,214,224,.62)", fontSize: 10 } },
      { scale: true, position: "right", gridIndex: 1, splitLine: { lineStyle: { color: "rgba(255,255,255,.045)", type: "dashed" } }, axisLabel: { color: "rgba(209,214,224,.48)", fontSize: 10 } },
      { scale: false, position: "right", gridIndex: 2, min: 0, max: 100, splitLine: { lineStyle: { color: "rgba(255,255,255,.045)", type: "dashed" } }, axisLabel: { color: "rgba(209,214,224,.45)", fontSize: 10 } },
    ],
    series,
  };
}

export function buildErrorOption(message: string) {
  return {
    backgroundColor: "#12161f",
    graphic: [{ type: "text", left: "center", top: "middle", style: { text: `行情加载失败\n${message}\n请稍后重试，或切换周期/品种。`, fill: "rgba(228,232,240,.76)", fontSize: 13, fontWeight: 500, lineHeight: 24, textAlign: "center", fontFamily: "Inter, Noto Sans SC, sans-serif" } }],
  };
}
