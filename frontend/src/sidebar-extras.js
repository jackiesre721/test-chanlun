import { ANALYZE_LIMIT } from "./constants.js";
import { apiPrefix } from "./api.js";
import { escHtml } from "./utils.js";
import { state } from "./state.js";
import { setRiskEntryPrice } from "./dom-fill.js";
import { render } from "./render.js";

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
  const symbol = document.getElementById("btSymbol")?.value || "BTCUSDT";
  const interval = document.getElementById("interval")?.value || "60";
  const startTimeInput = document.getElementById("btStartTime")?.value;
  const endTimeInput = document.getElementById("btEndTime")?.value;
  const strategy = document.getElementById("btStrategy")?.value || "long_only_flip";
  const feeBps = Number(document.getElementById("btFeeBps")?.value ?? "10");
  const leverage = Math.max(1, Math.min(100, Number(document.getElementById("btLeverage")?.value || "1")));
  const initialEquity = Number(document.getElementById("btEquity")?.value || "10000");
  const tradeAmountInput = document.getElementById("btTradeAmount")?.value;
  const tradeAmount = tradeAmountInput ? Number(tradeAmountInput) : null;

  let startTimeMs = null;
  if (startTimeInput) {
    startTimeMs = new Date(startTimeInput).getTime();
    if (!startTimeMs || isNaN(startTimeMs)) {
      out.innerHTML = `<span class="warn">开始时间格式无效</span>`;
      return;
    }
  }
  let endTimeMs = null;
  if (endTimeInput) {
    endTimeMs = new Date(endTimeInput).getTime();
    if (!endTimeMs || isNaN(endTimeMs)) {
      out.innerHTML = `<span class="warn">结束时间格式无效</span>`;
      return;
    }
  }

  btn.disabled = true;
  out.innerHTML = `<span class="muted">回测运行中…（较长样本可能需数十秒）</span>`;
  try {
    const prefix = apiPrefix();
    const body = {
      market: "crypto",
      symbol,
      interval,
      strategy,
      fee_bps: feeBps,
      leverage,
      initial_equity_usdt: initialEquity,
    };
    if (tradeAmount && tradeAmount > 0) body.trade_amount_usdt = tradeAmount;
    if (startTimeMs) body.start_time_ms = startTimeMs;
    if (endTimeMs) body.end_time_ms = endTimeMs;
    const res = await fetch(`${prefix}/backtest/quick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const raw = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(formatHttpError(raw, res));
    const m = raw.metrics || {};
    const disc = raw.disclaimer ? `<div class="muted" style="margin-bottom:10px;">${escHtml(raw.disclaimer)}</div>` : "";
    const tl = raw.trade_log || [];
    const tail = tl.length
      ? (() => {
          // Build trade pairs: each BUY opens, next SELL closes (or vice versa)
          const pairs = [];
          for (let i = 0; i < tl.length - 1; i++) {
            const open = tl[i], close = tl[i + 1];
            if ((open.action === "BUY" && close.action === "SELL") ||
                (open.action === "SELL" && close.action === "BUY")) {
              const isLong = open.action === "BUY";
              const pnl = isLong
                ? (close.price - open.price) * open.quantity
                : (open.price - close.price) * open.quantity;
              pairs.push({ open, close, isLong, pnl });
            }
          }
          const recent = pairs.slice(-10).reverse();
          if (!recent.length) return "";
          let html = `<details style="margin-top:10px;" id="btTradeDetails"><summary class="muted">最近 ${recent.length} 笔交易（点击行跳转）</summary>`;
          html += `<table class="bt-trade-table"><thead><tr><th>方向</th><th>开仓时间</th><th>开仓价</th><th>预估SL</th><th>预估TP1</th><th>平仓时间</th><th>平仓价</th><th>平仓原因</th><th>盈亏</th></tr></thead><tbody>`;
          for (const p of recent) {
            const dir = p.isLong ? '<span style="color:#00e676">多</span>' : '<span style="color:#ff1744">空</span>';
            const reason = p.close.exit_reason === "stop_loss"
              ? '<span style="color:#ff6e40">止损</span>'
              : '<span style="color:#69ff9e">信号</span>';
            const pnlColor = p.pnl >= 0 ? "#69ff9e" : "#ff6e40";
            const pnlSign = p.pnl >= 0 ? "+" : "";
            const slStr = p.open.stop_loss != null ? Number(p.open.stop_loss).toFixed(2) : "—";
            const tp1Str = p.open.take_profit_1 != null ? Number(p.open.take_profit_1).toFixed(2) : "—";
            html += `<tr style="cursor:pointer;" data-bt-time="${escHtml(p.close.time)}">
              <td>${dir}</td>
              <td>${escHtml(p.open.time)}</td>
              <td>${Number(p.open.price).toFixed(2)}</td>
              <td style="color:#ff6e40;">${slStr}</td>
              <td style="color:#69ff9e;">${tp1Str}</td>
              <td>${escHtml(p.close.time)}</td>
              <td>${Number(p.close.price).toFixed(2)}</td>
              <td>${reason}</td>
              <td style="color:${pnlColor};font-weight:700;">${pnlSign}${p.pnl.toFixed(2)}</td>
            </tr>`;
          }
          html += `</tbody></table></details>`;
          return html;
        })()
      : "";
    const wr = m.win_rate != null ? `<div>胜率：<b>${(Number(m.win_rate) * 100).toFixed(1)}%</b></div>` : "";
    const pf = m.profit_factor != null ? `<div>盈亏比：<b>${Number(m.profit_factor).toFixed(2)}</b></div>` : "";
    const sl = m.stop_loss_hits > 0 ? `<div>止损触发：<b>${m.stop_loss_hits}</b> 次</div>` : "";
    out.innerHTML =
      disc +
      `<div>bars：<b>${m.bars_used}</b>｜成交：<b>${m.trades}</b>｜终权益：<b>${Number(m.final_equity_usdt).toFixed(2)}</b> USDT</div>
      <div>总收益：<b>${(Number(m.total_return_fraction) * 100).toFixed(2)}%</b>｜最大回撤：<b>${(Number(m.max_drawdown_fraction) * 100).toFixed(2)}%</b></div>
      ${wr}${pf}${sl}
      ${
        m.sharpe_naive != null
          ? `<div>夏普（极简）：<b>${Number(m.sharpe_naive).toFixed(3)}</b></div>`
          : ""
      }
      <div class="muted" style="margin-top:10px;">已启用：止损(结构失效位)、仓位管理(按信号类型)、趋势过滤、盈亏比≥2:1</div>` +
      tail;
    // Store trades for chart overlay
    state.backtestTrades = tl.length ? tl : null;
    const overlayCb = document.getElementById("showBtOverlay");
    const overlayLabel = document.getElementById("btOverlayLabel");
    if (overlayCb) {
      overlayCb.disabled = !tl.length;
      if (overlayLabel) {
        overlayLabel.lastChild.textContent = tl.length ? " 图上显示回测交易点" : " 图上显示回测交易点（先运行回测）";
      }
    }
    if (state.lastResult && overlayCb?.checked) render(state.lastResult);
    // Make trade rows clickable to jump to K-line
    document.querySelectorAll("#btTradeDetails [data-bt-time]").forEach(row => {
      row.addEventListener("click", () => {
        const btTime = row.getAttribute("data-bt-time");
        if (!btTime || !state.lastResult?.kline_data?.length) return;
        const kd = state.lastResult.kline_data;
        const idx = kd.findIndex(k => k.time === btTime);
        if (idx < 0) return;
        const total = kd.length;
        const targetPct = (idx / (total - 1)) * 100;
        const halfWindow = 8;
        const start = Math.max(0, targetPct - halfWindow);
        const end = Math.min(100, targetPct + halfWindow);
        state.chart.dispatchAction({ type: "dataZoom", start, end });
      });
    });
  } catch (e) {
    out.innerHTML = `<span class="warn">${escHtml(e.message || String(e))}</span>`;
  } finally {
    btn.disabled = false;
  }
}

function syncBacktestDefaultsFromToolbar() {
  const sym = document.getElementById("symbol")?.value;
  const bts = document.getElementById("btSymbol");
  const bst = document.getElementById("btStartTime");
  const bet = document.getElementById("btEndTime");
  if (bts && sym) bts.value = sym;
  if (bst && !bst.value) {
    // Default: 6 months ago
    const d = new Date();
    d.setMonth(d.getMonth() - 6);
    bst.value = d.toISOString().slice(0, 16);
  }
  if (bet && !bet.value) {
    bet.value = new Date().toISOString().slice(0, 16);
  }
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

  document.getElementById("showBtOverlay")?.addEventListener("change", () => {
    if (state.lastResult) render(state.lastResult);
  });

  loadPaperRecent();
}
