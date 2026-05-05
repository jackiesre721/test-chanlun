import { ANALYZE_LIMIT } from "./constants.js";
import { escHtml } from "./utils.js";
import { state } from "./state.js";
import { render, showChartError } from "./render.js";
import { pickAdvancedContext, ensureAdvancedContextMerged } from "./advanced.js";
import { updateDisciplineRuleSnap, clearDisciplineRuleSnap } from "./discipline.js";

function analyzeApiUrl() {
  const p = apiPrefix();
  return `${p}/analyze`;
}

export function apiPrefix() {
  const el = document.querySelector("meta[name='chanlan-api-prefix']");
  return String((el && el.getAttribute("content")) || "").replace(/\/$/, "");
}

function unwrapAnalyzeBody(raw) {
  if (!raw || typeof raw !== "object") return raw;
  if (Array.isArray(raw.kline_data)) return raw;
  for (const k of ["data", "result", "payload", "body"]) {
    const inner = raw[k];
    if (inner && typeof inner === "object" && Array.isArray(inner.kline_data)) return inner;
  }
  return raw;
}

/** 主图分析成功后，把演示回测默认值对齐到当前品种/周期（便于假设检验）。 */
function syncBtInputsAfterAnalyze() {
  const sym = document.getElementById("symbol")?.value;
  const iv = document.getElementById("interval")?.value;
  const bts = document.getElementById("btSymbol");
  const bti = document.getElementById("btInterval");
  if (bts && sym) bts.value = sym;
  if (bti && iv) bti.value = iv;
}

export async function analyze() {
  document.body.classList.add("analyzing");
  document.getElementById("analyzeProgress").setAttribute("aria-busy", "true");
  document.getElementById("loading").style.display = "block";
  if (state.glmVerdictAbortController) state.glmVerdictAbortController.abort();
  state.glmVerdictAbortController = new AbortController();
  try {
    const payload = {
      market: "crypto",
      symbol: document.getElementById("symbol").value,
      interval: document.getElementById("interval").value,
      limit: ANALYZE_LIMIT,
    };
    const res = await fetch(analyzeApiUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const raw = await res.json();
    let advMerged = pickAdvancedContext(raw);
    const result = unwrapAnalyzeBody(raw);
    if (!advMerged) advMerged = pickAdvancedContext(result);
    if (advMerged && result.advanced_context == null && result.advancedContext == null) {
      result.advanced_context = advMerged;
    }
    if (result.success === false) throw new Error(result.error?.message || "分析失败");
    if (!Array.isArray(result.kline_data) || !result.kline_data.length) {
      throw new Error(
        "响应不是 analyze 形状（缺少 kline_data）。顶层键：" + Object.keys(raw || {}).join(", ")
      );
    }
    ensureAdvancedContextMerged(result);
    state.lastResult = result;
    document.getElementById("loading").style.display = "none";
    render(result);
    updateDisciplineRuleSnap(result);
    syncBtInputsAfterAnalyze();
  } catch (err) {
    clearDisciplineRuleSnap();
    showChartError(err.message || "分析失败");
    const vp = document.getElementById("verdictPanel");
    if (vp)
      vp.innerHTML = `<span class="warn">分析未完成：${escHtml(err.message || "未知错误")}</span><div class="muted" style="margin-top:10px;line-height:1.55;">可尝试：检查网络与后端健康（<code>/health</code>）；切换品种或周期；确认网关把 <code>POST /analyze</code> 指到本服务并重载页面。</div>`;
    document.getElementById("structureStatus").innerHTML = `<span class="warn">${err.message}</span>`;
    document.getElementById("advancedPanel").innerHTML = `<span class="warn">分析失败，无进阶结构数据</span>`;
    document.getElementById("actionFocus").innerHTML = `<span class="warn">分析失败，无法生成当下语境</span>`;
    document.getElementById("signalList").innerHTML = `<span class="warn">暂无信号</span>`;
  } finally {
    document.body.classList.remove("analyzing");
    document.getElementById("analyzeProgress").removeAttribute("aria-busy");
    document.getElementById("loading").style.display = "none";
  }
}
