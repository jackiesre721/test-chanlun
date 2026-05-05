import { state } from "./state.js";
import { KIND_NAME, SIGNAL_LEVEL_LABEL } from "./constants.js";
import { escHtml } from "./utils.js";
import { updateVisiblePriceScale } from "./zoom.js";
import { setRiskEntryPrice } from "./dom-fill.js";

let _chartSignalClickHandler = null;

function highlightSignalCard(idx) {
  document.querySelectorAll(".signal.signal-highlight").forEach(el => el.classList.remove("signal-highlight"));
  const card = document.querySelector(`#signalList [data-signal-idx="${idx}"]`);
  if (!card) return;
  card.classList.add("signal-highlight");
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  window.setTimeout(() => card.classList.remove("signal-highlight"), 2400);
}

function flashSidebarCardContaining(elementId) {
  const inner = document.getElementById(elementId);
  const card = inner && inner.closest(".card");
  if (!card) return;
  card.classList.add("sidebar-flash");
  window.setTimeout(() => card.classList.remove("sidebar-flash"), 1400);
}

/** 买卖点 / 背驰标注点击 → 缩放主图并联动侧栏 */
export function attachChartSignalClickHandlers(chart) {
  if (_chartSignalClickHandler) chart.off("click", _chartSignalClickHandler);
  _chartSignalClickHandler = params => {
    if (!params || params.componentType !== "series") return;
    const name = params.seriesName || "";
    const data = params.data;
    if (data && typeof data === "object" && !Array.isArray(data)) {
      if (data.chanSignalKind === "trade" && typeof data.chanSignalIdx === "number") {
        navigateToSignal(data.chanSignalIdx);
        highlightSignalCard(data.chanSignalIdx);
        return;
      }
      if (data.chanSignalKind === "divergence" && typeof data.chanSignalIdx === "number") {
        navigateToSignal(data.chanSignalIdx);
        document.getElementById("signalList")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        flashSidebarCardContaining("structureStatus");
        return;
      }
    }
    if ((name.includes("买点") || name.includes("卖点")) && Array.isArray(params.value)) {
      const idx = Number(params.value[0]);
      if (Number.isFinite(idx)) {
        navigateToSignal(idx);
        highlightSignalCard(idx);
      }
    }
    if (name === "背驰点" && Array.isArray(params.value)) {
      const idx = Number(params.value[0]);
      if (Number.isFinite(idx)) {
        navigateToSignal(idx);
        flashSidebarCardContaining("structureStatus");
      }
    }
  };
  chart.on("click", _chartSignalClickHandler);
}

function navigateToSignal(idx) {
  if (!state.lastResult || !state.lastResult.kline_data.length) return;
  const total = state.lastResult.kline_data.length;
  const windowSize = 16;
  const targetPct = (idx / (total - 1)) * 100;
  const halfWindow = windowSize / 2;
  const start = Math.max(0, targetPct - halfWindow);
  const end = Math.min(100, targetPct + halfWindow);
  state.chart.dispatchAction({ type: "dataZoom", start, end });
  updateVisiblePriceScale();
}

export function renderSignals(result) {
  const el = document.getElementById("signalList");
  if (!document.getElementById("showSignals").checked) {
    el.innerHTML =
      `<div class="muted">工具栏已关闭「买卖点」图层：图上与列表均隐藏；勾选后即可查看。</div>`;
    return;
  }
  const allSignals = [...result.buy_signals, ...result.sell_signals].sort((a, b) => b.idx - a.idx);
  const showFiltered = document.getElementById("showFilteredSignals")?.checked === true;
  const signals = showFiltered ? allSignals : allSignals.filter(s => !s.rr_filtered);
  if (!signals.length && !allSignals.length) {
    el.innerHTML = `<div class="muted">当前列表为空：多为<strong>结构不足以程序判定买卖点</strong>；若刚切换图层，请确认「买卖点」已勾选。</div>`;
    return;
  }
  if (!signals.length && allSignals.length) {
    el.innerHTML = `<div class="muted">${allSignals.length} 条信号被过滤（盈亏比不足或趋势不符）。勾选「含过滤信号」可查看。</div>`;
    return;
  }
  const block = signal => {
    const filteredTag = signal.rr_filtered ? '<span style="color:rgba(255,255,255,0.4);font-size:10px;margin-left:4px;">(过滤)</span>' : '';
    let sltpHtml = "";
    if (signal.stop_loss != null || signal.take_profit_1 != null || signal.take_profit != null) {
      const slLabel = signal.level === "segment" ? "SL(段)" : "SL";
      const slHtml = signal.stop_loss != null ? `<span>${slLabel}: <b style="color:#ff6e40">${Number(signal.stop_loss).toFixed(2)}</b></span>` : "";
      const sl2Html = signal.stop_loss_2 != null ? `<span>SL(笔): <b style="color:#ffab40">${Number(signal.stop_loss_2).toFixed(2)}</b></span>` : "";
      const tp1Html = signal.take_profit_1 != null ? `<span>TP1: <b style="color:#69ff9e">${Number(signal.take_profit_1).toFixed(2)}</b></span>` : "";
      const tp2Html = signal.take_profit != null ? `<span>TP2: <b style="color:#69ff9e">${Number(signal.take_profit).toFixed(2)}</b></span>` : "";
      sltpHtml = `<p style="font-size:11px;display:flex;gap:10px;flex-wrap:wrap;">${slHtml}${sl2Html}${tp1Html}${tp2Html}</p>`;
    }
    return `
    <div class="signal ${signal.side === "BUY" ? "buy" : "sell"}" data-signal-idx="${signal.idx}" style="cursor:pointer" title="点击跳转到图表对应位置">
      <div class="signal-head">
        <span><span class="pill ${signal.side === "BUY" ? "buy" : "sell"}">${signal.side === "BUY" ? "BUY" : "SELL"}</span> ${SIGNAL_LEVEL_LABEL[signal.level] || signal.level} ${KIND_NAME[signal.kind] || signal.kind}${signal.side === "BUY" ? "买" : "卖"}${filteredTag}</span>
        <span>${Number(signal.price).toFixed(2)}</span>
      </div>
      <p>${escHtml(signal.time)}｜${escHtml(signal.description)}</p>
      ${signal.evidence ? `<p>依据：${escHtml(signal.evidence)}</p>` : ""}
      ${sltpHtml}
    </div>
  `;
  };
  const head = 4;
  const vis = signals.slice(0, head);
  const rest = signals.slice(head);
  let html = `<div class="muted" style="margin-bottom:10px;">默认展示最近 <b>${vis.length}</b> 条结构快照（新→旧）。<b>点击信号卡片</b>可跳转图表。摘要请看最上方「当下简要结论」。完整列表可展开。</div>`;
  html += vis.map(s => block(s)).join("");
  if (rest.length) {
    html += `<details class="signal-more"><summary>再显示更早的 ${rest.length} 条信号</summary>${rest.map(s => block(s)).join("")}</details>`;
  }
  el.innerHTML = html;
  el.querySelectorAll("[data-signal-idx]").forEach(card => {
    card.addEventListener("click", () => {
      const idx = parseInt(card.dataset.signalIdx, 10);
      navigateToSignal(idx);
      const sig = signals.find(s => s.idx === idx);
      if (sig && sig.price != null) setRiskEntryPrice(sig.price);
    });
  });
}
