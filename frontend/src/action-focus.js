import { KIND_NAME } from "./constants.js";
import { escHtml, structureKindLabel } from "./utils.js";

function nearestPivotContainingLastBar(pivots, lastIdx) {
  if (!pivots.length) return null;
  const candidates = pivots.filter(p => lastIdx >= p.start_idx && lastIdx <= p.end_idx);
  if (!candidates.length) {
    return pivots.reduce((best, p) => (p.end_idx > best.end_idx ? p : best), pivots[0]);
  }
  return candidates.reduce((best, p) => (p.end_idx - p.start_idx > best.end_idx - best.start_idx ? p : best), candidates[0]);
}

function latestDivergenceNearEnd(divergences, sinceIdx) {
  const windowed = divergences.filter(d => d.idx >= sinceIdx);
  if (!windowed.length) return null;
  return windowed.reduce((a, b) => (a.idx > b.idx ? a : b));
}

function latestSignalNearEnd(signals, sinceIdx) {
  const windowed = signals.filter(s => s.idx >= sinceIdx);
  if (!windowed.length) return null;
  return windowed.reduce((a, b) => (a.idx > b.idx ? a : b));
}

function actionFocusHtmlFromApi(actionFocus, activeBiFallback) {
  const px = Number(actionFocus.current_price ?? 0);
  const lastIdx = Number(actionFocus.last_bar_index ?? 0);
  const recentBars = Number(actionFocus.recent_window_bars ?? 18);
  const dirLabel = d => d === "UP" ? "向上" : "向下";

  const slotLine = (label, slot) => {
    if (!slot || slot.relation === "none" || !slot.pivot) return `<div style="margin-top:8px;">${label}：当前无可用中枢参考。</div>`;
    const { zd, zg } = slot.pivot;
    if (slot.relation === "inside") {
      return `<div style="margin-top:8px;">${label}：价格 <b>${px.toFixed(2)}</b> 落在中枢 <b>[${Number(zd).toFixed(2)}, ${Number(zg).toFixed(2)}]</b> 内，属于中枢震荡语境。</div>`;
    }
    if (slot.relation === "above") {
      return `<div style="margin-top:8px;">${label}：价格 <b>${px.toFixed(2)}</b> 在中枢 <b>[${Number(zd).toFixed(2)}, ${Number(zg).toFixed(2)}]</b> 上方，属于偏强离开/回踩观察语境。</div>`;
    }
    return `<div style="margin-top:8px;">${label}：价格 <b>${px.toFixed(2)}</b> 在中枢 <b>[${Number(zd).toFixed(2)}, ${Number(zg).toFixed(2)}]</b> 下方，属于偏弱离开/反抽观察语境。</div>`;
  };

  const active = actionFocus.active_bi || activeBiFallback;
  let activeLine = `<div>未完成笔：暂无（等待新笔启动或结构太短）</div>`;
  if (active) {
    activeLine = `<div>未完成笔：<b>${dirLabel(active.direction)}</b>，${Number(active.start_price).toFixed(2)} → ${Number(active.end_price).toFixed(2)}（仅表示当下这一段<strong>尚未被反向分型确认</strong>）</div>`;
  }

  let divLine = `<div style="margin-top:8px;">最近窗口背驰：最近 ${recentBars} 根内<strong>未发现</strong>可对照的背驰候选。</div>`;
  if (actionFocus.recent_divergence) {
    const d = actionFocus.recent_divergence;
    const lvl = d.level === "bi" ? "笔" : "线段";
    const sk = structureKindLabel(d.structure_kind || "zpan_like");
    divLine = `<div style="margin-top:8px;">最近窗口背驰：<b>${lvl}</b>方向 <b>${d.direction === "DOWN" ? "底背驰语境" : "顶背驰语境"}</b>，<b>${sk}</b>，MACD 比 <b>${Number(d.ratio).toFixed(2)}</b>（仅说明力度对比，不代表此刻应下单）</div>`;
  }

  let hintLine = `<div style="margin-top:8px;color:rgba(232,236,246,.62);">无指令式买卖点，仅为结构语境披露。</div>`;
  if (actionFocus.recent_signal) {
    const s = actionFocus.recent_signal;
    const sideCn = s.side === "BUY" ? "买" : "卖";
    hintLine = `<div style="margin-top:8px;color:#ffbf69;"><b>结构锚点</b>：最近窗口曾标注<b>${KIND_NAME[s.kind] || s.kind}${sideCn}</b>（${s.time}），用于对照<strong>后续</strong>边界测试；<b>不是</b>「此刻必须进场」的指令。</div>`;
  }

  return `
    <div>最新价：<b>${px.toFixed(2)}</b>（最后一根 K 线索引 ${lastIdx}）</div>
    ${activeLine}
    ${slotLine("本级中枢", actionFocus.primary_pivot)}
    ${slotLine("中级别中枢", actionFocus.higher_pivot)}
    ${divLine}
    ${hintLine}
    <div style="margin-top:10px;font-size:11px;color:rgba(232,236,246,.48);">级别选择与风控责任说明见<strong>页脚风险提示</strong>。</div>
  `;
}

export function renderActionFocus(result) {
  const el = document.getElementById("actionFocus");
  if (!result.kline_data || !result.kline_data.length) {
    el.innerHTML = `<div class="muted">暂无 K 线数据</div>`;
    return;
  }
  if (result.action_focus) {
    el.innerHTML = actionFocusHtmlFromApi(result.action_focus, result.active_bi);
    return;
  }
  const lastIdx = result.kline_data.length - 1;
  const px = result.current_price;
  const dirLabel = d => d === "UP" ? "向上" : "向下";

  const recentBars = Math.max(18, Math.min(80, Math.floor(result.kline_data.length * 0.06)));
  const recentSince = lastIdx - recentBars;

  const lastPivot = nearestPivotContainingLastBar(result.zhongshus, lastIdx);
  let posText = "当前价格附近未落到已识别中枢区间内（或中枢列表为空）。";
  if (lastPivot) {
    const { zd, zg } = lastPivot;
    if (px >= zd && px <= zg) {
      posText = `价格 <b>${px.toFixed(2)}</b> 落在最近可视中枢 <b>[${zd.toFixed(2)}, ${zg.toFixed(2)}]</b> 内，属于中枢震荡语境。`;
    } else if (px > zg) {
      posText = `价格 <b>${px.toFixed(2)}</b> 在最近可视中枢 <b>[${zd.toFixed(2)}, ${zg.toFixed(2)}]</b> 上方，属于偏强离开/回踩观察语境。`;
    } else {
      posText = `价格 <b>${px.toFixed(2)}</b> 在最近可视中枢 <b>[${zd.toFixed(2)}, ${zg.toFixed(2)}]</b> 下方，属于偏弱离开/反抽观察语境。`;
    }
  }

  let activeLine = `<div>未完成笔：暂无（等待新笔启动或结构太短）</div>`;
  if (result.active_bi) {
    const ab = result.active_bi;
    activeLine = `<div>未完成笔：<b>${dirLabel(ab.direction)}</b>，${Number(ab.start_price).toFixed(2)} → ${Number(ab.end_price).toFixed(2)}（仅表示当下这一段<strong>尚未被反向分型确认</strong>）</div>`;
  }

  const lastDiv = latestDivergenceNearEnd(result.divergences, recentSince);
  let divLine = `<div style="margin-top:8px;">最近窗口背驰：最近 ${recentBars} 根内<strong>未发现</strong>可对照的背驰候选。</div>`;
  if (lastDiv) {
    const lvl = lastDiv.level === "bi" ? "笔" : "线段";
    const sk = structureKindLabel(lastDiv.structure_kind || "zpan_like");
    divLine = `<div style="margin-top:8px;">最近窗口背驰：<b>${lvl}</b>方向 <b>${lastDiv.direction === "DOWN" ? "底背驰语境" : "顶背驰语境"}</b>，<b>${sk}</b>，MACD 比 <b>${Number(lastDiv.ratio).toFixed(2)}</b>（仅说明力度对比，不代表此刻应下单）</div>`;
  }

  const recentSignal = latestSignalNearEnd([...result.buy_signals, ...result.sell_signals], recentSince);
  let hintLine = `<div style="margin-top:8px;color:rgba(232,236,246,.62);">无指令式买卖点，仅为结构语境披露。</div>`;
  if (recentSignal) {
    const sideCn = recentSignal.side === "BUY" ? "买" : "卖";
    hintLine = `<div style="margin-top:8px;color:#ffbf69;"><b>结构锚点</b>：最近窗口曾标注<b>${KIND_NAME[recentSignal.kind] || recentSignal.kind}${sideCn}</b>（${recentSignal.time}），用于对照<strong>后续</strong>边界测试；<b>不是</b>「此刻必须进场」的指令。</div>`;
  }

  el.innerHTML = `
    <div>最新价：<b>${px.toFixed(2)}</b>（最后一根 K 线索引 ${lastIdx}）</div>
    ${activeLine}
    <div style="margin-top:8px;">${posText}</div>
    ${divLine}
    ${hintLine}
    <div style="margin-top:10px;font-size:11px;color:rgba(232,236,246,.48);">级别选择与风控责任说明见<strong>页脚风险提示</strong>。</div>
  `;
}
