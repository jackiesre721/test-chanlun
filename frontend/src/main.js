import { state } from "./state.js";
import { LAYER_PRESETS, LAYER_SERIES_MAP } from "./constants.js";
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
  try {
    const prefix = (document.querySelector("meta[name='chanlan-api-prefix']")?.getAttribute("content") || "").replace(/\/$/, "");
    const res = await fetch(`${prefix}/api/symbols`);
    const data = await res.json();
    const banner = document.getElementById("symbolRegistryBanner");
    if (!res.ok) {
      if (banner) banner.hidden = false;
      throw new Error("bad response");
    }
    if (banner) banner.hidden = !data.registry_degraded;

    if (data.success && Array.isArray(data.symbols) && data.symbols.length > 0) {
      const sel = document.getElementById("symbol");
      const prev = sel.value || "BTCUSDT";
      sel.innerHTML = "";
      data.symbols.forEach(s => {
        const o = document.createElement("option");
        o.value = s;
        o.textContent = s;
        if (s === prev) o.selected = true;
        sel.appendChild(o);
      });
    }
  } catch (e) {
    const banner = document.getElementById("symbolRegistryBanner");
    if (banner) banner.hidden = false;
    const warn = document.getElementById("warning");
    if (warn) warn.textContent = "品种列表加载失败，使用默认列表。";
  }
}

// Event bindings
document.getElementById("analyzeBtn").addEventListener("click", analyze);
document.getElementById("symbol").addEventListener("change", analyze);
document.getElementById("interval").addEventListener("change", analyze);

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

window.addEventListener("resize", () => state.chart.resize());

await loadDynamicSymbols();
analyze();
