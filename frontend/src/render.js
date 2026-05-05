import { CHART_PALETTE, ANALYZE_LIMIT, LAYER_SERIES_MAP } from "./constants.js";
import { escHtml, fmtOpenTime } from "./utils.js";
import { state } from "./state.js";
import { updateVisiblePriceScale } from "./zoom.js";
import { attachChartSignalClickHandlers, renderSignals } from "./signals.js";
import { renderVerdictPanel } from "./verdict.js";
import { renderAdvancedPanel } from "./advanced.js";
import { renderActionFocus } from "./action-focus.js";

function fractalChartX(f) {
  if (!f) return 0;
  const n = f.norm_idx;
  if (n != null && Number.isFinite(Number(n))) return Number(n);
  return Number(f.idx);
}

function strokeSeries(name, strokes, len, color, width, dashed) {
  const data = Array(len).fill(null);
  for (const stroke of strokes) {
    data[stroke.start_idx] = stroke.start_price;
    data[stroke.end_idx] = stroke.end_price;
  }
  const lineStyle = { color, width };
  if (dashed) lineStyle.type = "dashed";
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 5,
    data, connectNulls: true, symbol: "circle", symbolSize: 5,
    lineStyle, itemStyle: { color }, emphasis: { disabled: true }
  };
}

function segmentPolylineSeries(name, segments, bis, len, color, width) {
  const b = bis || [];
  const segs = segments || [];
  if (!segs.length || !b.length || !len) return null;
  const data = Array(len).fill(null);
  const fillStrokeSpan = st => {
    if (!st) return;
    const ns = st.norm_start_idx != null ? Number(st.norm_start_idx) : Number(st.start_idx);
    const ne = st.norm_end_idx != null ? Number(st.norm_end_idx) : Number(st.end_idx);
    const a = Math.min(ns, ne);
    const z = Math.max(ns, ne);
    let pa = st.start_price;
    let pz = st.end_price;
    if (ns !== a) { pa = st.end_price; pz = st.start_price; }
    const span = z - a;
    if (span <= 0) { if (a >= 0 && a < len) data[a] = pa; return; }
    for (let k = a; k <= z && k < len; k++) {
      const t = (k - a) / span;
      data[k] = pa + (pz - pa) * t;
    }
  };
  for (const seg of segs) {
    const lo = Math.max(0, Math.floor(Number(seg.start_bi)));
    const hi = Math.min(b.length - 1, Math.floor(Number(seg.end_bi)));
    if (hi < lo) continue;
    for (let i = lo; i <= hi; i++) fillStrokeSpan(b[i]);
  }
  const has = data.some(v => v != null);
  if (!has) return null;
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 8,
    data, connectNulls: false, showSymbol: false, symbol: "none",
    lineStyle: {
      color, width, cap: "round", join: "round",
      shadowBlur: 10, shadowColor: "rgba(255,167,38,0.45)", shadowOffsetY: 0
    },
    itemStyle: { color }, emphasis: { disabled: true }
  };
}

function activeStrokeSeries(name, stroke, len) {
  const data = Array(len).fill(null);
  data[stroke.start_idx] = stroke.start_price;
  data[stroke.end_idx] = stroke.end_price;
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 5,
    data, connectNulls: true, symbol: "circle", symbolSize: 6,
    lineStyle: { color: CHART_PALETTE.activeBi, width: 2, type: "dashed" },
    itemStyle: { color: CHART_PALETTE.activeBi }, emphasis: { disabled: true }
  };
}

function fractalSeries(fractals) {
  const list = fractals || [];
  const tentTop = f => f.type === "TOP" && f.confirmed === false;
  const okTop = f => f.type === "TOP" && f.confirmed !== false;
  const tentBot = f => f.type === "BOTTOM" && f.confirmed === false;
  const okBot = f => f.type === "BOTTOM" && f.confirmed !== false;
  const withStrength = f => {
    const v = [fractalChartX(f), f.price];
    const s = f.strength_hint != null ? Math.round(Number(f.strength_hint) * 100) : null;
    return s != null ? { value: v, fractalStrength: s } : { value: v };
  };
  return [
    {
      name: "顶分型", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 6,
      symbol: "triangle", symbolSize: 10, symbolRotate: 180,
      itemStyle: { color: CHART_PALETTE.fractalTop, borderColor: CHART_PALETTE.fractalTopBorder, borderWidth: 1 },
      label: { show: true, position: "top", distance: 2, fontSize: 9, color: "#e1bee7", formatter: p => (p.data.fractalStrength != null ? p.data.fractalStrength + "%" : "") },
      data: list.filter(okTop).map(withStrength)
    },
    {
      name: "顶分型(进行中)", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 5,
      symbol: "triangle", symbolSize: 7, symbolRotate: 180,
      itemStyle: { color: CHART_PALETTE.fractalTopTent, borderColor: CHART_PALETTE.fractalTopBorder, borderWidth: 1 },
      label: { show: true, position: "top", fontSize: 8, color: "#e1bee7", formatter: "?" },
      data: list.filter(tentTop).map(f => [fractalChartX(f), f.price])
    },
    {
      name: "底分型", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 6,
      symbol: "triangle", symbolSize: 10,
      itemStyle: { color: CHART_PALETTE.fractalBottom, borderColor: CHART_PALETTE.fractalBottomBorder, borderWidth: 1 },
      label: { show: true, position: "bottom", distance: 2, fontSize: 9, color: "#c8e6c9", formatter: p => (p.data.fractalStrength != null ? p.data.fractalStrength + "%" : "") },
      data: list.filter(okBot).map(withStrength)
    },
    {
      name: "底分型(进行中)", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 5,
      symbol: "triangle", symbolSize: 7,
      itemStyle: { color: CHART_PALETTE.fractalBottomTent, borderColor: CHART_PALETTE.fractalBottomBorder, borderWidth: 1 },
      label: { show: true, position: "bottom", fontSize: 8, color: "#c8e6c9", formatter: "?" },
      data: list.filter(tentBot).map(f => [fractalChartX(f), f.price])
    }
  ];
}

function pivotSeries(name, pivots, palettePivot) {
  const fill = palettePivot && typeof palettePivot === "object" ? palettePivot.fill : palettePivot;
  const border = palettePivot && typeof palettePivot === "object" ? palettePivot.border : "rgba(255,255,255,0.35)";
  const segBand = name.indexOf("线段") !== -1;
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 1,
    data: [], silent: true, tooltip: { show: false },
    markArea: {
      silent: true,
      itemStyle: {
        color: fill, borderColor: border, borderWidth: 1.25,
        borderType: segBand ? "dashed" : "solid",
        shadowBlur: 8, shadowColor: "rgba(0,0,0,0.45)",
      },
      data: pivots.map(p => [{ xAxis: p.start_idx, yAxis: p.zd }, { xAxis: p.end_idx, yAxis: p.zg }]),
    },
  };
}

function divergenceScatterSeries(divergences) {
  return {
    name: "背驰点", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 12,
    symbol: "diamond", symbolSize: 13,
    itemStyle: { borderColor: "#eceff1", borderWidth: 1.5 },
    label: {
      show: true, position: "top", distance: 3, fontSize: 10, fontWeight: 700,
      color: CHART_PALETTE.divergenceLabel, textBorderColor: "#263238", textBorderWidth: 2,
      formatter(p) {
        const d = p.data?.dv;
        if (!d) return "背驰";
        return d.structure_kind === "trend" ? "趋势背驰" : "盘整背驰";
      }
    },
    data: (divergences || []).map(d => ({
      value: [d.idx, d.price],
      dv: d,
      chanSignalKind: "divergence",
      chanSignalIdx: d.idx,
      itemStyle: { color: d.direction === "DOWN" ? CHART_PALETTE.divergenceDown : CHART_PALETTE.divergenceUp }
    })),
    emphasis: { scale: 1.35 }
  };
}

function biPauseScatterSeries(bis) {
  const pts = (bis || [])
    .filter(b => b.pause_after_end === true)
    .map(b => {
      const x = b.norm_end_idx != null ? b.norm_end_idx : b.end_idx;
      return { value: [x, b.end_price] };
    });
  if (!pts.length) return null;
  return {
    name: "笔停顿", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 11,
    symbol: "pin", symbolSize: 11,
    itemStyle: { color: CHART_PALETTE.pause, borderColor: CHART_PALETTE.pauseBorder, borderWidth: 1 },
    label: { show: true, position: "bottom", distance: 2, fontSize: 9, color: "#fffde7", formatter: "停顿" },
    data: pts
  };
}

function linesFormGraphic(result) {
  const lf = result.lines_form;
  if (!lf || !lf.primary) return [];
  const det = lf.detail_zh ? String(lf.detail_zh) : "";
  const detShort = det.length > 52 ? det.slice(0, 52) + "…" : det;
  const eng = result.segment_engine === "strict67" ? "67课特征序列" : "legacy 三笔重叠";
  const text = `走势形态：${lf.primary}${detShort ? " ｜ " + detShort : ""} ｜ ${eng}`;
  return [
    {
      type: "text", left: 52, top: 40, z: 80,
      style: {
        text, fill: CHART_PALETTE.linesFormText,
        font: "700 11px system-ui, -apple-system, sans-serif",
        width: Math.min(window.innerWidth * 0.55, 720),
        overflow: "truncate"
      }
    }
  ];
}

function signalSeries(name, signals, color, symbolShape) {
  return {
    name, type: "scatter", xAxisIndex: 0, yAxisIndex: 0, z: 13,
    symbol: symbolShape, symbolSize: 17,
    itemStyle: { color, borderColor: "#263238", borderWidth: 1.5 },
    data: signals.map(s => ({
      value: [s.idx, s.price],
      chanSignalKind: "trade",
      chanSignalIdx: s.idx,
      chanSignalSide: s.side,
      itemStyle: { color, borderColor: "#263238", borderWidth: 1.5 },
    }))
  };
}

function fakeBiSeries(name, fakeBis, len) {
  if (!fakeBis || !fakeBis.length) return null;
  const data = Array(len).fill(null);
  for (const fb of fakeBis) {
    if (fb.start_idx >= 0 && fb.start_idx < len) data[fb.start_idx] = fb.start_price;
    if (fb.end_idx >= 0 && fb.end_idx < len) data[fb.end_idx] = fb.end_price;
  }
  return {
    name, type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 2,
    data, connectNulls: true, symbol: "none",
    lineStyle: { color: CHART_PALETTE.fakeBi, width: 1, type: "dashed" }
  };
}

function renderStructureStatus(result) {
  const el = document.getElementById("structureStatus");
  const lastBi = result.bis[result.bis.length - 1];
  const active = result.active_bi;
  const biPivots = result.zhongshus.filter(pivot => pivot.level === "bi").length;
  const segmentPivots = result.zhongshus.filter(pivot => pivot.level === "segment").length;
  const segEngine = result.segment_engine === "strict67" ? "67课特征序列（strict67）" : "legacy（三笔重叠+延伸）";
  const directionLabel = dir => dir === "UP" ? "上升" : "下降";
  el.innerHTML = `
    <div>确认笔数量：<b>${result.bis.length}</b></div>
    <div>本级分型数量：<b>${result.fractals.length}</b></div>
    <div>线段划分引擎：<b>${segEngine}</b></div>
    <div>线段数量：<b>${result.segments.length}</b></div>
    <div>笔中枢数量：<b>${biPivots}</b></div>
    <div>线段中枢数量：<b>${segmentPivots}</b></div>
    <div>背驰候选：<b>${result.divergences.length}</b>（趋势/盘整类见一类买卖点说明与依据）</div>
    ${result.lines_form ? `<div style="margin-top:10px;">走势形态：<b>${result.lines_form.primary}</b> — ${result.lines_form.detail_zh}${result.lines_form.abc_hint ? `<div style="margin-top:6px;color:rgba(232,236,246,.62);">${result.lines_form.abc_hint}</div>` : ""}</div>` : ""}
    ${lastBi ? `<div style="margin-top:8px;">最后确认笔：${directionLabel(lastBi.direction)}，${Number(lastBi.start_price).toFixed(2)} → ${Number(lastBi.end_price).toFixed(2)}</div>` : ""}
    ${active ? `<div style="margin-top:8px;color:#f1d28a;">当前未完成笔：${directionLabel(active.direction)}，${Number(active.start_price).toFixed(2)} → ${Number(active.end_price).toFixed(2)}</div>` : `<div style="margin-top:8px;">暂无未完成笔。</div>`}
    <div style="margin-top:10px;font-size:11px;color:rgba(232,236,246,.5);">进阶明细见卡片「进阶结构」。合规说明见页脚。</div>
  `;
}

export function showChartError(message) {
  state.chart.setOption({
    backgroundColor: "#12161f",
    graphic: [
      {
        type: "text", left: "center", top: "middle",
        style: {
          text: `行情加载失败\n${message}\n请稍后重试，或切换周期/品种。`,
          fill: "rgba(228,232,240,.76)", fontSize: 13, fontWeight: 500,
          lineHeight: 24, textAlign: "center",
          fontFamily: "Inter, Noto Sans SC, sans-serif",
        },
      },
    ],
  }, true);
}

export function render(result) {
  const times = result.kline_data.map(k => k.time);
  const candles = result.kline_data.map(k => [k.open, k.close, k.low, k.high]);
  const macdBars = result.macd_data.map(m => m.hist);
  const dif = result.macd_data.map(m => m.dif);
  const dea = result.macd_data.map(m => m.dea);
  const series = [
    {
      name: "K线", type: "candlestick", data: candles, xAxisIndex: 0, yAxisIndex: 0, z: 3,
      itemStyle: { color: CHART_PALETTE.kUp, color0: CHART_PALETTE.kDown, borderColor: CHART_PALETTE.kUp, borderColor0: CHART_PALETTE.kDown },
      markLine: {
        symbol: "none",
        data: [{ yAxis: result.current_price, label: { formatter: result.current_price.toFixed(2) } }],
        lineStyle: { color: CHART_PALETTE.priceLine, type: "dashed" }
      }
    }
  ];

  const zhAll = result.zhongshus || [];
  const biPivots = zhAll.filter(p => p.level === "bi");
  const segmentPivots = zhAll.filter(p => p.level === "segment");
  series.push(strokeSeries("本级笔", result.bis, times.length, CHART_PALETTE.bi, 2));
  if (result.active_bi) series.push(activeStrokeSeries("未完成笔", result.active_bi, times.length));
  {
    const pauseS = biPauseScatterSeries(result.bis);
    if (pauseS) series.push(pauseS);
  }
  series.push(...fractalSeries(result.fractals));
  series.push(signalSeries("买点", result.buy_signals, CHART_PALETTE.signalBuy, "triangle"));
  series.push(signalSeries("卖点", result.sell_signals, CHART_PALETTE.signalSell, "pin"));
  if (result.divergences && result.divergences.length) {
    series.push(divergenceScatterSeries(result.divergences));
  }
  series.push(strokeSeries("上级笔", result.bis_lv2, times.length, CHART_PALETTE.higherBi, 2, true));
  if (biPivots.length) {
    series.push(pivotSeries("笔中枢带", biPivots, CHART_PALETTE.pivotBi));
  }
  if (segmentPivots.length) {
    series.push(pivotSeries("线段中枢带", segmentPivots, CHART_PALETTE.pivotSegment));
  }
  if (result.zhongshus_lv2 && result.zhongshus_lv2.length) {
    series.push(pivotSeries("上级中枢", result.zhongshus_lv2, CHART_PALETTE.pivotHigher));
  }
  {
    const sp = segmentPolylineSeries("线段", result.segments, result.bis, times.length, CHART_PALETTE.segment, 4);
    if (sp) series.push(sp);
  }
  const boll = result.bollinger || [];
  if (boll.length === times.length) {
    series.push({ name: "BOLL上", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 4, data: boll.map(b => b.upper), symbol: "none", lineStyle: { width: 1, color: CHART_PALETTE.bollUpper } });
    series.push({ name: "BOLL中", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 4, data: boll.map(b => b.mid), symbol: "none", lineStyle: { width: 1, type: "dotted", color: CHART_PALETTE.bollMid } });
    series.push({ name: "BOLL下", type: "line", xAxisIndex: 0, yAxisIndex: 0, z: 4, data: boll.map(b => b.lower), symbol: "none", lineStyle: { width: 1, color: CHART_PALETTE.bollLower } });
  }
  if (result.fake_bis && result.fake_bis.length) {
    const fxs = fakeBiSeries("FakeBI", result.fake_bis, times.length);
    if (fxs) series.push(fxs);
  }
  series.push({
    name: "MACD", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: macdBars,
    itemStyle: { color: value => value.data >= 0 ? CHART_PALETTE.macdPos : CHART_PALETTE.macdNeg }
  });
  series.push({
    name: "DIF", type: "line", xAxisIndex: 1, yAxisIndex: 1, data: dif, symbol: "none",
    lineStyle: { color: CHART_PALETTE.dif, width: 1.5 },
    markLine: {
      silent: true, symbol: "none",
      lineStyle: { color: CHART_PALETTE.zeroLine, width: 1, type: "dashed" },
      label: { show: true, formatter: "0", color: "rgba(209,212,220,.5)", fontSize: 9 },
      data: [{ yAxis: 0 }]
    }
  });
  series.push({ name: "DEA", type: "line", xAxisIndex: 1, yAxisIndex: 1, data: dea, symbol: "none", lineStyle: { color: CHART_PALETTE.dea, width: 1.5 } });
  const rsiA = result.rsi14 || [];
  if (rsiA.length === times.length) {
    series.push({
      name: "RSI14", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: rsiA, symbol: "none",
      lineStyle: { color: CHART_PALETTE.rsiLine, width: 1.2 },
      markLine: { silent: true, symbol: "none", lineStyle: { color: "rgba(255,255,255,.2)", type: "dashed" }, data: [{ yAxis: 70 }, { yAxis: 30 }] }
    });
  }

  const subCompact = document.getElementById("compactSubplots")?.checked === true;
  const legendTop = subCompact ? 4 : 10;
  const legendSelected = {};
  for (const [checkboxId, seriesNames] of Object.entries(LAYER_SERIES_MAP)) {
    const checked = document.getElementById(checkboxId)?.checked ?? true;
    for (const name of seriesNames) legendSelected[name] = checked;
  }
  const chartGrids = subCompact
    ? [
        { left: 48, right: 68, top: 28, height: "58%" },
        { left: 48, right: 68, top: "67%", height: "9%" },
        { left: 48, right: 68, top: "78%", height: "9%" },
      ]
    : [
        { left: 50, right: 70, top: 46, height: "46%" },
        { left: 50, right: 70, top: "60%", height: "10%" },
        { left: 50, right: 70, top: "72%", height: "10%" },
      ];

  state.chart.setOption({
    backgroundColor: "#12161f",
    animation: false,
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
        crossStyle: { color: "rgba(255,255,255,.22)", width: 1 },
        label: { backgroundColor: "rgba(18,22,31,.92)", borderColor: "rgba(255,255,255,.08)", color: "#e8eaf0" },
      },
      backgroundColor: "rgba(14,17,24,.94)",
      borderColor: "rgba(255,255,255,.09)",
      borderWidth: 1,
      padding: [10, 13],
      extraCssText: "border-radius:8px;box-shadow:0 12px 40px rgba(0,0,0,.45);",
      textStyle: { color: "#e8eaf0", fontSize: 11, fontFamily: "Inter, Noto Sans SC, sans-serif" },
      formatter(params) {
        if (!params || !params.length) return "";
        const ax = params[0].axisValueLabel || params[0].name || "";
        const idx = params[0].dataIndex;
        const kd = state.lastResult && state.lastResult.kline_data;
        const k = kd && typeof idx === "number" && idx >= 0 && idx < kd.length ? kd[idx] : null;
        let headLine = ax;
        if (k != null && k.open_time != null) {
          headLine = `<div style="font-weight:800;margin-bottom:4px;">北京时间（UTC+8） ${fmtOpenTime(k.open_time)}</div><div style="opacity:.82;font-size:11px;">轴标 ${escHtml(String(ax))}</div>`;
        }
        const lines = [headLine];
        for (const q of params) {
          const s = q.seriesName || "";
          if (q.seriesType === "candlestick" && q.data && q.data.length >= 4) {
            const [o, c, l, h] = q.data;
            lines.push(`${s} O=${o} H=${h} L=${l} C=${c}`);
            continue;
          }
          if (q.seriesType === "scatter") {
            const d = q.data;
            const dv = d && d.dv;
            if (dv) { lines.push(`${s}：${dv.description || ""}`); continue; }
            if (d && d.chanSignalKind === "trade") {
              lines.push(`${s}：索引 ${d.chanSignalIdx}（点击联动侧栏卡片）`);
              continue;
            }
            if (d && d.fractalStrength != null) { lines.push(`${s} 力度≈${d.fractalStrength}%`); continue; }
          }
          if (q.value != null && Array.isArray(q.value)) {
            lines.push(`${s} ${q.value.map(v => (typeof v === "number" ? Number(v).toFixed(4) : v)).join(", ")}`);
          } else if (q.value != null) {
            lines.push(`${s} ${q.value}`);
          }
        }
        return lines.join("<br/>");
      }
    },
    legend: {
      type: "scroll", top: legendTop, itemGap: 12, icon: "roundRect", itemWidth: 10, itemHeight: 10,
      selected: legendSelected,
      pageIconColor: "rgba(228,232,240,.45)",
      pageTextStyle: { color: "rgba(228,232,240,.45)", fontSize: 10 },
      textStyle: { color: "rgba(228,232,240,.72)", fontSize: 11, fontFamily: "Inter, Noto Sans SC, sans-serif" },
    },
    graphic: linesFormGraphic(result),
    axisPointer: { link: [{ xAxisIndex: [0, 1, 2] }] },
    grid: chartGrids,
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1, 2], start: 64, end: 100, filterMode: "none" },
      {
        type: "slider", xAxisIndex: [0, 1, 2], start: 64, end: 100, bottom: 10, height: 20, filterMode: "none",
        backgroundColor: "rgba(0,0,0,.28)", borderColor: "rgba(255,255,255,.06)",
        fillerColor: "rgba(79,139,255,.16)", handleStyle: { color: "#4580ff", borderColor: "rgba(255,255,255,.2)" },
        textStyle: { color: "rgba(228,232,240,.42)", fontSize: 10 },
        moveHandleStyle: { color: "rgba(79,139,255,.35)" },
      },
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
    series
  }, { notMerge: true, lazyUpdate: true });
  updateVisiblePriceScale();

  document.getElementById("warning").textContent = result.warning || "";
  const meta = document.getElementById("dataMetaLine");
  if (meta) {
    meta.innerHTML =
      `数据来自 ${result.data_source}；规则版本 ${result.rules_version}；K 线为<strong>合并后</strong>（与分型/笔/指标索引一致）；线段 ${result.segment_engine === "strict67" ? "67课特征序列(strict67)" : "legacy三笔重叠"}；本次响应 <strong>${result.kline_data.length}</strong> 根合并 K（请求 limit=<strong>${ANALYZE_LIMIT}</strong>）。`;
  }
  renderVerdictPanel(result);
  renderStructureStatus(result);
  renderAdvancedPanel(result);
  renderActionFocus(result);
  renderSignals(result);
  attachChartSignalClickHandlers(state.chart);
}
