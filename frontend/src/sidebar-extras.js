import { ANALYZE_LIMIT } from "./constants.js";
import { apiPrefix } from "./api.js";
import { escHtml } from "./utils.js";
import { state } from "./state.js";
import { setRiskEntryPrice } from "./dom-fill.js";

const INTERVAL_LABEL = {
  "1": "1m",
  "15": "15m",
  "30": "30m",
  "60": "1h",
  "240": "4h",
  "1440": "1d",
};

function intervalsForMulti(currentInterval) {
  const presets = {
    "1": ["15", "60", "240"],
    "15": ["60", "240", "1440"],
    "30": ["60", "240", "1440"],
    "60": ["240", "1440"],
    "240": ["60", "1440"],
    "1440": ["60", "240"],
  };
  return presets[currentInterval] || ["60", "240", "1440"];
}

function formatHttpError(raw, res) {
  const d = raw && raw.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(x => (typeof x === "object" && x.msg ? x.msg : JSON.stringify(x))).join("; ");
  if (d && typeof d === "object") return JSON.stringify(d);
  return raw?.message || `HTTP ${res.status}`;
}

async function fetchMultiAnalyze(symbol, intervals) {
  const prefix = apiPrefix();
  const res = await fetch(`${prefix}/analyze/multi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      market: "crypto",
      symbol,
      intervals,
      limit: ANALYZE_LIMIT,
    }),
  });
  const raw = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(formatHttpError(raw, res));
  return raw;
}

function renderMultiTable(resp) {
  const el = document.getElementById("multiTfOut");
  if (!el) return;
  const rows = resp.results || [];
  if (!rows.length) {
    el.innerHTML = `<span class="muted">无结果</span>`;
    return;
  }
  let html =
    `<table class="multi-tf-table"><thead><tr><th>周期</th><th>bars</th><th>买/卖</th><th>现价</th><th></th></tr></thead><tbody>`;
  for (const row of rows) {
    const r = row.result || {};
    const iv = row.interval || "";
    const lb = INTERVAL_LABEL[iv] || iv;
    const buys = (r.buy_signals || []).length;
    const sells = (r.sell_signals || []).length;
    const px = r.current_price != null ? Number(r.current_price).toFixed(4) : "—";
    html += `<tr>
      <td><b>${lb}</b></td>
      <td>${(r.kline_data || []).length}</td>
      <td>${buys}/${sells}</td>
      <td>${px}</td>
      <td><button type="button" class="multi-open-btn" data-interval="${escHtml(iv)}">主图打开</button></td>
    </tr>`;
  }
  html += `</tbody></table>`;
  el.innerHTML = html;
  el.querySelectorAll(".multi-open-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const iv = btn.getAttribute("data-interval");
      const sel = document.getElementById("interval");
      if (sel && iv) {
        sel.value = iv;
        document.getElementById("analyzeBtn")?.click();
      }
      document.querySelector(".sidebar")?.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

async function onMultiTfLoad() {
  const out = document.getElementById("multiTfOut");
  const btn = document.getElementById("multiTfBtn");
  if (!out || !btn) return;
  const symbol = document.getElementById("symbol")?.value || "BTCUSDT";
  const curIv = document.getElementById("interval")?.value || "240";
  const intervals = intervalsForMulti(curIv);
  btn.disabled = true;
  out.innerHTML = `<span class="muted">加载中… (${intervals.map(i => INTERVAL_LABEL[i] || i).join(", ")})</span>`;
  try {
    const resp = await fetchMultiAnalyze(symbol, intervals);
    renderMultiTable(resp);
  } catch (e) {
    out.innerHTML = `<span class="warn">${escHtml(e.message || String(e))}</span>`;
  } finally {
    btn.disabled = false;
  }
}

async function submitPaper(side) {
  const sym = document.getElementById("symbol")?.value || "BTCUSDT";
  const qty = Number(document.getElementById("paperQty")?.value || "0");
  const note = document.getElementById("paperNote")?.value?.trim() || "";
  const status = document.getElementById("paperStatus");
  if (!(qty > 0)) {
    if (status) status.textContent = "数量须大于 0";
    return;
  }
  const prefix = apiPrefix();
  const res = await fetch(`${prefix}/trade/paper`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol: sym, side, quantity: qty, note }),
  });
  const raw = await res.json().catch(() => ({}));
  if (!status) return;
  if (raw.accepted) status.textContent = `已记账 ${raw.order_id?.slice(0, 8) || ""}…`;
  else status.textContent = raw.reason || "未接受";
  loadPaperRecent();
}

async function loadPaperRecent() {
  const el = document.getElementById("paperRecent");
  if (!el) return;
  try {
    const prefix = apiPrefix();
    const res = await fetch(`${prefix}/trade/paper/recent?limit=12`);
    const raw = await res.json();
    const orders = raw.orders || [];
    if (!orders.length) {
      el.innerHTML = `<span class="muted">暂无记录</span>`;
      return;
    }
    el.innerHTML = orders
      .map(
        o => `<div class="paper-row"><span class="pill ${o.side === "BUY" ? "buy" : "sell"}">${o.side}</span>
        <span>${escHtml(o.symbol)}</span> × ${Number(o.quantity).toFixed(4)}
        <span class="muted">${escHtml(o.note || "")}</span></div>`
      )
      .join("");
  } catch {
    el.innerHTML = `<span class="warn">加载失败</span>`;
  }
}

async function computeRiskSize() {
  const out = document.getElementById("riskOut");
  if (!out) return;
  const equity = Number(document.getElementById("riskEquity")?.value || "0");
  const rf = Number(document.getElementById("riskFrac")?.value || "0");
  const entry = Number(document.getElementById("riskEntry")?.value || "0");
  const stop = Number(document.getElementById("riskStop")?.value || "0");
  out.innerHTML = "";
  if (!(equity > 0 && rf > 0 && entry > 0 && stop > 0)) {
    out.innerHTML = `<span class="muted">请填写账户权益、风险比例、入场价与止损价</span>`;
    return;
  }
  let advisory = "";
  if (rf > 0.02) {
    advisory = `<div class="risk-warn-strong">单笔风险比例 &gt;2%，多数系统化实盘视为过激；请确认已与熔断、月度回撤容忍对齐。</div>`;
  } else if (rf > 0.01) {
    advisory = `<div class="risk-warn-mid">单笔风险比例 &gt;1%，偏离常见自省区间（0.25%～1%）较多。</div>`;
  } else if (rf > 0 && rf < 0.002) {
    advisory = `<div class="risk-warn-soft">比例 &lt;0.2%/笔：名义头寸可能过小，执行与噪声占比上升。</div>`;
  }
  try {
    const prefix = apiPrefix();
    const res = await fetch(`${prefix}/risk/position-size`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        equity_usdt: equity,
        risk_fraction: rf,
        entry_price: entry,
        stop_price: stop,
      }),
    });
    const raw = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(formatHttpError(raw, res));
    out.innerHTML =
      advisory +
      `<div>风险预算：<b>${Number(raw.risk_usdt).toFixed(2)}</b> USDT</div>
      <div>建议数量：<b>${Number(raw.suggested_quantity).toFixed(6)}</b></div>
      <div>名义：<b>${Number(raw.notional_usdt).toFixed(2)}</b> USDT</div>`;
  } catch (e) {
    out.innerHTML = advisory + `<span class="warn">${escHtml(e.message || String(e))}</span>`;
  }
}

async function runQuickBacktest() {
  const out = document.getElementById("btOut");
  const btn = document.getElementById("btRunBtn");
  if (!out || !btn) return;
  const symbol = document.getElementById("btSymbol")?.value?.trim() || "BTCUSDT";
  const interval = document.getElementById("btInterval")?.value?.trim() || "240";
  const maxBars = Number(document.getElementById("btMaxBars")?.value || "6000");
  const strategy = document.getElementById("btStrategy")?.value || "long_only_flip";
  const feeBps = Number(document.getElementById("btFeeBps")?.value ?? "10");
  const initialEquity = Number(document.getElementById("btEquity")?.value || "10000");
  btn.disabled = true;
  out.innerHTML = `<span class="muted">回测运行中…（较长样本可能需数十秒）</span>`;
  try {
    const prefix = apiPrefix();
    const res = await fetch(`${prefix}/backtest/quick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        market: "crypto",
        symbol,
        interval,
        max_bars: maxBars,
        strategy,
        fee_bps: feeBps,
        initial_equity_usdt: initialEquity,
      }),
    });
    const raw = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(formatHttpError(raw, res));
    const m = raw.metrics || {};
    const disc = raw.disclaimer ? `<div class="muted" style="margin-bottom:10px;">${escHtml(raw.disclaimer)}</div>` : "";
    const tl = raw.trade_log || [];
    const tail = tl.length
      ? `<details style="margin-top:10px;"><summary class="muted">最近成交 ${Math.min(8, tl.length)} 笔</summary>${tl
          .slice(-8)
          .map(
            t =>
              `<div class="paper-row">${escHtml(t.action)} ${escHtml(t.time)} @ ${Number(t.price).toFixed(4)} eq=${Number(t.equity_after).toFixed(2)}</div>`
          )
          .join("")}</details>`
      : "";
    out.innerHTML =
      disc +
      `<div>bars：<b>${m.bars_used}</b>｜成交：<b>${m.trades}</b>｜终权益：<b>${Number(m.final_equity_usdt).toFixed(2)}</b> USDT</div>
      <div>总收益（比例）：<b>${(Number(m.total_return_fraction) * 100).toFixed(2)}%</b>｜最大回撤：<b>${(Number(m.max_drawdown_fraction) * 100).toFixed(2)}%</b></div>
      ${
        m.sharpe_naive != null
          ? `<div>夏普（极简）：<b>${Number(m.sharpe_naive).toFixed(3)}</b></div>`
          : ""
      }
      <div class="muted" style="margin-top:10px;">对照<strong>规则快照</strong>做多品种 / 多窗口样本外解读；失效形态常为震荡磨损或单边踏空。</div>` +
      tail;
  } catch (e) {
    out.innerHTML = `<span class="warn">${escHtml(e.message || String(e))}</span>`;
  } finally {
    btn.disabled = false;
  }
}

function syncBacktestDefaultsFromToolbar() {
  const sym = document.getElementById("symbol")?.value;
  const iv = document.getElementById("interval")?.value;
  const bts = document.getElementById("btSymbol");
  const bti = document.getElementById("btInterval");
  if (bts && sym && !(bts.value || "").trim()) bts.value = sym;
  if (bti && iv && !(bti.value || "").trim()) bti.value = iv;
}

export function initSidebarExtras() {
  syncBacktestDefaultsFromToolbar();

  document.getElementById("multiTfBtn")?.addEventListener("click", () => onMultiTfLoad());

  document.getElementById("paperBuyBtn")?.addEventListener("click", () => submitPaper("BUY"));
  document.getElementById("paperSellBtn")?.addEventListener("click", () => submitPaper("SELL"));
  document.getElementById("paperReloadBtn")?.addEventListener("click", () => loadPaperRecent());

  document.getElementById("riskFillFromChartBtn")?.addEventListener("click", () => {
    const px = state.lastResult?.current_price;
    setRiskEntryPrice(px);
  });

  document.getElementById("riskComputeBtn")?.addEventListener("click", () => computeRiskSize());

  document.getElementById("btRunBtn")?.addEventListener("click", () => runQuickBacktest());

  loadPaperRecent();
}
