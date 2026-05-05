import { RECURSION_COMP_LABEL, KIND_NAME } from "./constants.js";
import { escHtml } from "./utils.js";
import { pickAdvancedContext } from "./advanced.js";
import { state } from "./state.js";

function pickAdvancedForVerdict(result) {
  return pickAdvancedContext(result) ?? result.advanced_context ?? result.advancedContext;
}

export function computeVerdict(result) {
  const bullets = [];
  if (!result.kline_data || !result.kline_data.length) {
    return { headline: "—", sub: "暂无 K 线。", bullets: [], tone: "hold" };
  }
  const buys = result.buy_signals || [];
  const sells = result.sell_signals || [];
  const all = [...buys, ...sells];
  if (!all.length) {
    bullets.push("同级别中枢、离开段与背驰证据不足时，本页不输出买卖点。");
    return {
      headline: "暂不操作（无买卖点）",
      sub: "当前更像在等结构完成；没有可依赖的「指令式买/卖」标签。",
      bullets,
      tone: "hold"
    };
  }
  const latest = all.reduce((a, b) => (a.idx >= b.idx ? a : b));
  const kn = KIND_NAME[latest.kind] || latest.kind;
  bullets.push(
    `后续可先盯住：价格相对最近中枢边界（ZD/ZG）的突破与回抽如何演化；时间上最近标注点为${latest.side === "BUY" ? "买" : "卖"}侧 ${kn}（${latest.time || "—"}），仅作价位与结构锚点，不代表此刻操作。`
  );
  let headline = "观望（有历史点）";
  let tone = "hold";
  let sub =
    "图上有历史买卖点标注时，默认把它当作「下一步对照用的参考位」，重点放在边界测试与未完成结构如何延续，而非复述已走完的行情。";
  if (latest.side === "BUY") {
    headline = "偏多观察";
    tone = "bull";
    sub =
      "结构上最近标注在买侧；后续优先看回抽/下探在中枢边界附近是否获得支撑或失效，而不是把已过买点当成「现在就该入场」。";
  } else {
    headline = "偏空观察";
    tone = "bear";
    sub =
      "结构上最近标注在卖侧；后续优先看上冲/回抽在中枢边界附近是否遇阻或失效，而不是把已过卖点当成「现在就该离场」。";
  }
  const af = result.action_focus;
  const rel = af && af.primary_pivot ? af.primary_pivot.relation : null;
  if (rel === "inside") bullets.push("本级：价在最近参考中枢区间内 → 震荡为主；下一步看突破哪一侧并能否站稳。");
  else if (rel === "above") bullets.push("本级：价在最近参考中枢之上 → 下一步重点看回踩 ZG 一带能否守住。");
  else if (rel === "below") bullets.push("本级：价在最近参考中枢之下 → 下一步重点看反抽 ZD 一带能否站回。");

  const adv = pickAdvancedForVerdict(result);
  if (adv && adv.trend_recursion && adv.trend_recursion.composite) {
    const comp = adv.trend_recursion.composite;
    const lab = RECURSION_COMP_LABEL[comp] || comp;
    bullets.push(`跨级：${lab}——解读时优先看各级边界与离开段是否共振，少用单边口号定型。`);
    if (comp === "cross_level_divergent") {
      if (tone === "bull") headline = "偏多观察（跨级背离）";
      else if (tone === "bear") headline = "偏空观察（跨级背离）";
      else headline = "跨级背离（观望优先）";
      tone = "warn";
    }
  }
  const active = (af && af.active_bi) || result.active_bi;
  if (active && latest) {
    const penUp = active.direction === "UP";
    const lateBuy = latest.side === "BUY";
    if (penUp && !lateBuy)
      bullets.push(
        "未完成笔向上与更近的卖侧锚点并存：下一步看这笔是否延伸、何时被反向分型终结，以及边界测试结果。"
      );
    if (!penUp && lateBuy)
      bullets.push(
        "未完成笔向下与更近的买侧锚点并存：下一步看这笔是否延伸、何时被反向分型终结，以及边界测试结果。"
      );
  }
  return { headline, sub, bullets, tone };
}

function verdictApiUrlsInOrder() {
  const el = document.querySelector("meta[name='chanlan-api-prefix']");
  const prefix = (el && el.getAttribute("content")) || "";
  const p = String(prefix).replace(/\/$/, "");
  return [...new Set([`${p}/analyze/verdict`, `${p}/ai/verdict`, `${p}/api/ai/verdict`])];
}

function stripForVerdictPayload(result) {
  const o = structuredClone(result);
  o.kline_data = [];
  o.macd_data = [];
  o.bollinger = [];
  o.rsi14 = [];
  o.fractals = [];
  o.fake_bis = [];
  o.kline_parent_refs = [];
  if (Array.isArray(o.bis) && o.bis.length > 16) o.bis = o.bis.slice(-16);
  if (Array.isArray(o.bis_lv2) && o.bis_lv2.length > 12) o.bis_lv2 = o.bis_lv2.slice(-12);
  return o;
}

const GLM_LS_KEY = "chanlan_glm_api_key";
const GLM_LS_MODEL = "chanlan_glm_model";
const GLM_LS_FULL = "chanlan_glm_full_context";

function buildVerdictRequestBody(result) {
  const fullEl = document.getElementById("glmFullContext");
  const full = fullEl ? fullEl.checked : true;
  let o;
  if (full) {
    o = structuredClone(result);
  } else {
    o = stripForVerdictPayload(result);
  }
  const keyEl = document.getElementById("glmApiKey");
  const modelEl = document.getElementById("glmModel");
  const k = keyEl && keyEl.value.trim();
  if (k) o.glm_api_key = k;
  const m = modelEl && modelEl.value.trim();
  if (m) o.glm_model = m;
  o.glm_full_context = full;
  return o;
}

function applyGlmVerdict(aiVerdict) {
  const glmEl = document.getElementById("verdictGlmBlock");
  if (!glmEl) return;
  if (!aiVerdict || aiVerdict.success === false) {
    const msg = (aiVerdict && aiVerdict.summary_zh) || "未能生成 AI 摘要。";
    glmEl.innerHTML = `<div class="warn" style="margin-top:10px;">${escHtml(msg)}</div>`;
    return;
  }
  if (!aiVerdict.summary_zh) {
    glmEl.innerHTML = `<div class="warn" style="margin-top:10px;">响应缺少 summary_zh</div>`;
    return;
  }
  const biasMap = { long: "偏多", short: "偏空", neutral: "观望 / 中性" };
  const biasZh = biasMap[aiVerdict.bias] || aiVerdict.bias;
  const src =
    aiVerdict.source === "glm"
      ? `智谱 ${escHtml(aiVerdict.model_name || "GLM")}`
      : aiVerdict.source === "heuristic_fallback"
        ? "规则摘要（后端降级）"
        : escHtml(String(aiVerdict.source || "—"));
  const conf =
    typeof aiVerdict.confidence === "number" ? Math.round(aiVerdict.confidence * 100) : null;
  const reasons = Array.isArray(aiVerdict.reasons_zh) ? aiVerdict.reasons_zh : [];
  const rlist =
    reasons.length > 0
      ? `<ul style="margin:8px 0 0 18px;font-size:12px;color:rgba(232,236,246,.72);line-height:1.65;">${reasons.map(x => `<li>${escHtml(x)}</li>`).join("")}</ul>`
      : "";
  const errLine = aiVerdict.error_detail
    ? `<div class="adv-note" style="margin-top:6px;color:rgba(255,191,105,.88);">${escHtml(aiVerdict.error_detail)}</div>`
    : "";
  const disc = aiVerdict.disclaimer
    ? `<div class="adv-note" style="margin-top:8px;">${escHtml(aiVerdict.disclaimer)}</div>`
    : "";
  const ph = aiVerdict.price_hints;
  let priceBlock = "";
  if (ph && typeof ph === "object") {
    const fmtPrice = x => {
      if (x == null || x === "") return "—";
      const n = Number(x);
      if (!Number.isFinite(n)) return escHtml(String(x));
      const s = n.toFixed(10).replace(/\.?0+$/, "");
      return escHtml(s || String(n));
    };
    priceBlock = `
    <div class="adv-note" style="margin-top:10px;padding:10px;border-radius:8px;background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.08);">
      <div style="font-weight:900;color:#b8c5ff;margin-bottom:6px;">参考价位（推演用）</div>
      <div>买侧参考：<b style="color:#19e6a6">${fmtPrice(ph.buy_focus_price)}</b>｜卖侧参考：<b style="color:#7fb7ff">${fmtPrice(ph.sell_focus_price)}</b></div>
      <div style="margin-top:4px;">止损观察（多）：${fmtPrice(ph.stop_loss_buy)}｜止损观察（空）：${fmtPrice(ph.stop_loss_sell)}</div>
      ${ph.note_zh ? `<div class="adv-note" style="margin-top:6px;">${escHtml(ph.note_zh)}</div>` : ""}
    </div>`;
  }
  glmEl.innerHTML = `
    <div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(255,255,255,.1);">
      <div style="font-size:11px;font-weight:900;color:rgba(241,210,138,.95);letter-spacing:.06em;">AI 语境摘要（含参考价，非下单指令）</div>
      <div style="margin-top:8px;font-size:15px;font-weight:900;color:#e8ecf6;">${escHtml(biasZh)}${conf != null ? ` · 置信 ${conf}%` : ""}</div>
      <div class="muted" style="margin-top:6px;font-size:13px;line-height:1.55;">${escHtml(aiVerdict.summary_zh)}</div>
      ${priceBlock}
      ${rlist}
      <div class="adv-note" style="margin-top:8px;">来源：${src}</div>
      ${errLine}
      ${disc}
    </div>
  `;
}

async function loadVerdictAi(result) {
  const glmEl = document.getElementById("verdictGlmBlock");
  const use = document.getElementById("useGlmVerdict");
  if (!glmEl) return;
  if (use && !use.checked) {
    glmEl.innerHTML = "";
    return;
  }
  if (result.glm_verdict) {
    applyGlmVerdict(result.glm_verdict);
    return;
  }
  glmEl.innerHTML = `<span class="muted">正在异步请求智谱摘要（不阻塞上图）…</span>`;
  try {
    const bodyJson = JSON.stringify(buildVerdictRequestBody(result));
    const sig = state.glmVerdictAbortController ? state.glmVerdictAbortController.signal : undefined;
    const postJson = url =>
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: bodyJson,
        signal: sig,
      });
    const urls = verdictApiUrlsInOrder();
    let res = null;
    let raw = null;
    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      res = await postJson(url);
      try {
        raw = await res.json();
      } catch {
        raw = { detail: res.statusText || "non-json body" };
      }
      if (res.ok) break;
      if (res.status !== 404) break;
    }
    if (!res || !res.ok) {
      const detail =
        raw && typeof raw.detail === "string"
          ? raw.detail
          : Array.isArray(raw?.detail)
            ? JSON.stringify(raw.detail)
            : res
              ? res.statusText
              : "no response";
      const nf =
        res && res.status === 404
          ? `<div class="adv-note" style="margin-top:8px;">已按顺序请求：${escHtml(urls.join(" → "))}。若均为 404，请升级/重启本仓库后端（需含 <code>/analyze/verdict</code>），或让网关转发上述路径之一。</div>`
          : "";
      glmEl.innerHTML = `<div class="warn" style="margin-top:10px;">GLM 接口错误：${escHtml(detail)}</div>${nf}`;
      return;
    }
    applyGlmVerdict(raw);
  } catch (e) {
    if (e && e.name === "AbortError") return;
    glmEl.innerHTML = `<div class="warn" style="margin-top:10px;">GLM 请求失败：${escHtml(e.message || String(e))}</div>`;
  }
}

export function loadGlmSettingsFromStorage() {
  try {
    const k = localStorage.getItem(GLM_LS_KEY);
    const m = localStorage.getItem(GLM_LS_MODEL);
    const f = localStorage.getItem(GLM_LS_FULL);
    const keyEl = document.getElementById("glmApiKey");
    const modelEl = document.getElementById("glmModel");
    const fullEl = document.getElementById("glmFullContext");
    if (keyEl && k) keyEl.value = k;
    if (modelEl && m) modelEl.value = m;
    if (fullEl && f !== null) fullEl.checked = f !== "0";
  } catch (e) {
    /* ignore */
  }
}

export function saveGlmSettingsToStorage() {
  const keyEl = document.getElementById("glmApiKey");
  const modelEl = document.getElementById("glmModel");
  const fullEl = document.getElementById("glmFullContext");
  const note = document.getElementById("glmSaveNote");
  try {
    localStorage.setItem(GLM_LS_KEY, (keyEl && keyEl.value) || "");
    localStorage.setItem(GLM_LS_MODEL, (modelEl && modelEl.value.trim()) || "glm-4.7");
    localStorage.setItem(GLM_LS_FULL, fullEl && fullEl.checked ? "1" : "0");
    if (note) note.textContent = "已保存。";
  } catch (e) {
    if (note) note.textContent = "保存失败（可能为隐私模式）。";
  }
}

export function renderVerdictPanel(result) {
  const el = document.getElementById("verdictPanel");
  if (!el) return;
  const v = computeVerdict(result);
  const colors = { bull: "#19e6a6", bear: "#7fb7ff", hold: "rgba(232,236,246,.9)", warn: "#ffb74d" };
  const color = colors[v.tone] || colors.hold;
  const list =
    v.bullets.length > 0
      ? `<ul style="margin:12px 0 0 18px;font-size:12px;color:rgba(232,236,246,.72);line-height:1.65;">${v.bullets.map(b => `<li>${escHtml(b)}</li>`).join("")}</ul>`
      : "";
  el.innerHTML = `
    <div style="font-size:20px;font-weight:950;color:${color};letter-spacing:.04em;line-height:1.25;">${escHtml(v.headline)}</div>
    <div class="muted" style="margin-top:10px;font-size:13px;line-height:1.55;">${escHtml(v.sub)}</div>
    ${list}
    <div style="margin-top:12px;font-size:11px;color:rgba(232,236,246,.48);">合规与免责声明见<strong>页脚</strong>。</div>
    <div id="verdictGlmBlock"></div>
  `;
  loadVerdictAi(result);
}
