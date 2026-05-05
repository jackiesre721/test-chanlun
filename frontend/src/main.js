import { state } from "./state.js";
import { LAYER_PRESETS, LAYER_SERIES_MAP, HIGHER_INTERVAL_LABEL } from "./constants.js";
import { analyze } from "./api.js";
import { render } from "./render.js";
import { loadGlmSettingsFromStorage, saveGlmSettingsToStorage, renderVerdictPanel } from "./verdict.js";
import { scheduleVisiblePriceScaleFromDataZoom } from "./zoom.js";
import { initSidebarExtras } from "./sidebar-extras.js";
import { initDisciplineUi } from "./discipline.js";
import "./style.css";

state.chart = echarts.init(document.getElementById("chart"));

function applyLayerPreset(name) {
  const p = LAYER_PRESETS[name];
  if (!p) return;
  Object.entries(p).forEach(([id, v]) => {
    const el = document.getElementById(id);
    if (el) el.checked = v;
  });
  try { localStorage.setItem("chanlan_layer_preset", name); } catch (e) { /* ignore */ }
  if (state.lastResult) render(state.lastResult);
}

function initLayerPresetFromStorage() {
  try {
    const saved = localStorage.getItem("chanlan_layer_preset");
    const p = saved && LAYER_PRESETS[saved];
    if (!p) return;
    Object.entries(p).forEach(([id, v]) => {
      const el = document.getElementById(id);
      if (el) el.checked = v;
    });
  } catch (e) { /* ignore */ }
}

function syncToolbarToggleLabel() {
  const collapsed = document.body.classList.contains("chart-layout-compact-toolbar");
  const btn = document.getElementById("toggleCompactToolbar");
  if (btn) btn.textContent = collapsed ? "展开控件" : "收起控件";
}

function syncSidebarToggleLabel() {
  const hidden = document.body.classList.contains("chart-layout-hide-sidebar");
  const btn = document.getElementById("toggleSidebar");
  if (btn) btn.textContent = hidden ? "显示侧栏" : "隐藏侧栏";
}

function syncSegmentLabels() {
  const iv = document.getElementById("interval")?.value || "240";
  const hiLabel = HIGHER_INTERVAL_LABEL[iv] || "";
  const segLabel = document.querySelector('label[for="showSegments"]') || document.getElementById("showSegments")?.closest("label");
  const segPivotLabel = document.querySelector('label[for="showZhongshuSeg"]') || document.getElementById("showZhongshuSeg")?.closest("label");
  if (segLabel) {
    const cb = segLabel.querySelector("input");
    const base = "线段";
    segLabel.lastChild.textContent = hiLabel ? ` ${base}（≈${hiLabel}笔）` : ` ${base}`;
  }
  if (segPivotLabel) {
    const cb = segPivotLabel.querySelector("input");
    const base = "线段中枢带";
    segPivotLabel.lastChild.textContent = hiLabel ? ` ${base}（≈${hiLabel}中枢）` : ` ${base}`;
  }
}

function initChartLayoutPreferences() {
  try {
    if (localStorage.getItem("chanlan_toolbar_collapsed") === "1") {
      document.body.classList.add("chart-layout-compact-toolbar");
    }
    if (localStorage.getItem("chanlan_hide_sidebar") === "1") {
      document.body.classList.add("chart-layout-hide-sidebar");
    }
    const cs = document.getElementById("compactSubplots");
    if (cs && localStorage.getItem("chanlan_compact_subplots") === "1") cs.checked = true;
  } catch (e) { /* ignore */ }
  syncToolbarToggleLabel();
  syncSidebarToggleLabel();
}

async function loadDynamicSymbols() {
  // Fixed whitelist — no dynamic fetch needed.
}

// Event bindings
document.getElementById("analyzeBtn").addEventListener("click", analyze);
document.getElementById("symbol").addEventListener("change", analyze);
document.getElementById("interval").addEventListener("change", () => { syncSegmentLabels(); analyze(); });

document.querySelectorAll(".preset-btn[data-preset]").forEach(btn => {
  btn.addEventListener("click", () => applyLayerPreset(btn.getAttribute("data-preset")));
});

document.getElementById("toggleCompactToolbar")?.addEventListener("click", () => {
  document.body.classList.toggle("chart-layout-compact-toolbar");
  try {
    localStorage.setItem(
      "chanlan_toolbar_collapsed",
      document.body.classList.contains("chart-layout-compact-toolbar") ? "1" : "0"
    );
  } catch (e) { /* ignore */ }
  syncToolbarToggleLabel();
  state.chart.resize();
});

document.getElementById("toggleSidebar")?.addEventListener("click", () => {
  document.body.classList.toggle("chart-layout-hide-sidebar");
  try {
    localStorage.setItem(
      "chanlan_hide_sidebar",
      document.body.classList.contains("chart-layout-hide-sidebar") ? "1" : "0"
    );
  } catch (e) { /* ignore */ }
  syncSidebarToggleLabel();
  state.chart.resize();
});

document.getElementById("compactSubplots")?.addEventListener("change", () => {
  try {
    localStorage.setItem(
      "chanlan_compact_subplots",
      document.getElementById("compactSubplots")?.checked ? "1" : "0"
    );
  } catch (e) { /* ignore */ }
  if (state.lastResult) render(state.lastResult);
  else state.chart.resize();
});

initLayerPresetFromStorage();
initChartLayoutPreferences();
syncSegmentLabels();
loadGlmSettingsFromStorage();
initDisciplineUi();
initSidebarExtras();

document.getElementById("glmSaveBtn")?.addEventListener("click", saveGlmSettingsToStorage);
document.getElementById("useGlmVerdict")?.addEventListener("change", () => {
  if (state.lastResult) renderVerdictPanel(state.lastResult);
});
document.getElementById("glmFullContext")?.addEventListener("change", () => {
  if (state.lastResult) renderVerdictPanel(state.lastResult);
});

state.chart.on("dataZoom", scheduleVisiblePriceScaleFromDataZoom);

Object.keys(LAYER_SERIES_MAP).forEach(id => {
  document.getElementById(id).addEventListener("change", e => {
    if (!state.lastResult) return;
    const names = LAYER_SERIES_MAP[id];
    const checked = e.target.checked;
    names.forEach(name => {
      state.chart.dispatchAction({ type: checked ? "legendSelect" : "legendUnSelect", name });
    });
  });
});
// 段中枢开关同时控制段级信号的渲染，需要完整重绘
document.getElementById("showZhongshuSeg")?.addEventListener("change", () => {
  if (state.lastResult) render(state.lastResult);
});
// 过滤信号开关需要完整重绘（动态添加/移除 series）
document.getElementById("showFilteredSignals")?.addEventListener("change", () => {
  if (state.lastResult) render(state.lastResult);
});

window.addEventListener("resize", () => state.chart.resize());

await loadDynamicSymbols();
analyze();
