import type {
  AnalyzeResult,
  PositionSizeRequest,
  PositionSizeResponse,
  PaperTradeRequest,
  PaperTradeRecord,
  BacktestRequest,
  BacktestResult,
  BacktestExecTrade,
  SymbolOption,
} from "@/types/analysis";

function apiPrefix(): string {
  const el = document.querySelector("meta[name='chanlan-api-prefix']");
  return String(el?.getAttribute("content") || "").replace(/\/$/, "");
}

function unwrapAnalyzeBody(raw: unknown): AnalyzeResult {
  if (!raw || typeof raw !== "object") return raw as AnalyzeResult;
  const r = raw as Record<string, unknown>;
  if (Array.isArray(r.kline_data)) return raw as AnalyzeResult;
  for (const k of ["data", "result", "payload", "body"]) {
    const inner = r[k];
    if (inner && typeof inner === "object" && Array.isArray((inner as Record<string, unknown>).kline_data)) {
      return inner as AnalyzeResult;
    }
  }
  return raw as AnalyzeResult;
}

export async function postAnalyze(symbol: string, interval: string): Promise<AnalyzeResult> {
  const res = await fetch(`${apiPrefix()}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ market: "crypto", symbol, interval, limit: 2500 }),
  });
  const raw = await res.json();
  const result = unwrapAnalyzeBody(raw);
  if (result.success === false) throw new Error(result.error?.message || "分析失败");
  if (!Array.isArray(result.kline_data) || !result.kline_data.length) {
    throw new Error("响应缺少 kline_data。顶层键：" + Object.keys(raw || {}).join(", "));
  }
  // Merge advanced_context from wrapping levels if not on result directly
  if (!result.advanced_context) {
    const r = raw as Record<string, unknown>;
    for (const k of ["data", "result", "payload", "body"]) {
      const inner = r[k] as Record<string, unknown> | undefined;
      if (inner?.advanced_context) {
        result.advanced_context = inner.advanced_context as AnalyzeResult["advanced_context"];
        break;
      }
    }
  }
  return result;
}

export async function postMultiAnalyze(symbol: string, intervals: string[]): Promise<Record<string, AnalyzeResult>> {
  const res = await fetch(`${apiPrefix()}/analyze/multi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ market: "crypto", symbol, intervals }),
  });
  if (!res.ok) throw new Error(`多周期请求失败: ${res.status}`);
  return res.json();
}

export async function postRiskPositionSize(params: PositionSizeRequest): Promise<PositionSizeResponse> {
  const res = await fetch(`${apiPrefix()}/risk/position-size`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      equity_usdt: params.equity,
      risk_fraction: params.risk_fraction,
      entry_price: params.entry_price,
      stop_price: params.stop_price,
      leverage: params.leverage ?? 1,
      maint_margin_rate: params.maint_margin_rate,
    }),
  });
  if (!res.ok) throw new Error(`风控计算失败: ${res.status}`);
  const raw = (await res.json()) as Record<string, unknown>;
  return {
    quantity: Number(raw.suggested_quantity ?? 0),
    notional: Number(raw.notional_usdt ?? 0),
    risk_amount: Number(raw.risk_usdt ?? 0),
    leverage: Number(raw.leverage ?? 1),
    required_margin: raw.required_margin != null ? Number(raw.required_margin) : undefined,
    liquidation_price: raw.liquidation_price != null ? Number(raw.liquidation_price) : undefined,
    effective_risk_pct: raw.effective_risk_pct != null ? Number(raw.effective_risk_pct) : undefined,
    warnings: Array.isArray(raw.warnings) ? (raw.warnings as string[]) : [],
  };
}

export async function postPaperTrade(params: PaperTradeRequest): Promise<PaperTradeRecord> {
  const res = await fetch(`${apiPrefix()}/trade/paper`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`纸盘交易失败: ${res.status}`);
  return res.json();
}

export async function getPaperRecent(): Promise<PaperTradeRecord[]> {
  const res = await fetch(`${apiPrefix()}/trade/paper/recent`);
  if (!res.ok) throw new Error(`获取纸盘记录失败: ${res.status}`);
  return res.json();
}

/** 将后端 `QuickBacktestResponse` 转为侧栏易用的扁平字段。 */
export function normalizeQuickBacktest(raw: Record<string, unknown>): BacktestResult {
  const m = raw.metrics as Record<string, unknown> | undefined;
  const closedRaw = raw.closed_trades;
  const closed = Array.isArray(closedRaw) ? closedRaw : [];

  const total_ret_frac = m ? Number(m.total_return_fraction ?? 0) : 0;
  const max_dd_frac = m ? Number(m.max_drawdown_fraction ?? 0) : 0;

  const statsRaw = raw.stats_by_signal_kind;
  const stats_by_signal_kind =
    statsRaw && typeof statsRaw === "object" && statsRaw !== null
      ? (statsRaw as BacktestResult["stats_by_signal_kind"])
      : undefined;

  const closed_trades = closed.map((row) => {
    const r = row as Record<string, unknown>;
    return {
      entry_bar_idx: r.entry_bar_idx != null ? Number(r.entry_bar_idx) : undefined,
      exit_bar_idx: r.exit_bar_idx != null ? Number(r.exit_bar_idx) : undefined,
      entry_time: String(r.entry_time ?? ""),
      exit_time: String(r.exit_time ?? ""),
      entry_price: Number(r.entry_price ?? 0),
      exit_price: Number(r.exit_price ?? 0),
      side: String(r.side ?? ""),
      pnl_usdt: Number(r.pnl_usdt ?? 0),
      pnl_pct: Number(r.pnl_pct ?? 0),
      bars_held: Number(r.bars_held ?? 0),
      signal_kind_at_entry: String(r.signal_kind_at_entry ?? ""),
    };
  });

  const logRaw = raw.trade_log;
  const trade_log: BacktestExecTrade[] = Array.isArray(logRaw)
    ? logRaw.map((row) => {
        const r = row as Record<string, unknown>;
        const act = String(r.action ?? "").toUpperCase();
        return {
          bar_idx: Number(r.bar_idx ?? 0),
          time: String(r.time ?? ""),
          action: act === "SELL" ? "SELL" : "BUY",
          price: Number(r.price ?? 0),
          equity_after: Number(r.equity_after ?? 0),
          exit_reason: r.exit_reason != null ? String(r.exit_reason) : undefined,
          quantity: r.quantity != null ? Number(r.quantity) : undefined,
          stop_loss: r.stop_loss != null ? Number(r.stop_loss) : undefined,
          take_profit_1: r.take_profit_1 != null ? Number(r.take_profit_1) : undefined,
          take_profit_2: r.take_profit_2 != null ? Number(r.take_profit_2) : undefined,
        };
      })
    : [];

  return {
    success: raw.success !== false,
    disclaimer: typeof raw.disclaimer === "string" ? raw.disclaimer : undefined,
    total_return_pct: total_ret_frac * 100,
    max_drawdown_pct: max_dd_frac * 100,
    sharpe_ratio: m?.sharpe_naive != null ? Number(m.sharpe_naive) : undefined,
    trade_count: m ? Number(m.trades ?? 0) : 0,
    bars_used: m ? Number(m.bars_used ?? 0) : undefined,
    final_equity_usdt: m ? Number(m.final_equity_usdt ?? 0) : undefined,
    closed_trade_count:
      m?.closed_trade_count != null ? Number(m.closed_trade_count) : closed_trades.length,
    win_rate_pct: m?.win_rate != null ? Number(m.win_rate) * 100 : undefined,
    profit_factor: m?.profit_factor != null ? Number(m.profit_factor) : undefined,
    expectancy_per_trade_usdt:
      m?.expectancy_per_trade_usdt != null ? Number(m.expectancy_per_trade_usdt) : undefined,
    max_consecutive_losses:
      m?.max_consecutive_losses != null ? Number(m.max_consecutive_losses) : undefined,
    avg_win_usdt: m?.avg_win_usdt != null ? Number(m.avg_win_usdt) : undefined,
    avg_loss_usdt: m?.avg_loss_usdt != null ? Number(m.avg_loss_usdt) : undefined,
    stop_loss_hits: m?.stop_loss_hits != null ? Number(m.stop_loss_hits) : undefined,
    closed_trades,
    trade_log,
    stats_by_signal_kind,
  };
}

export async function postBacktestQuick(params: BacktestRequest): Promise<BacktestResult> {
  const body: Record<string, unknown> = {
    market: "crypto",
    symbol: params.symbol,
    interval: String(params.interval),
    strategy: params.strategy,
    fee_bps: params.fee_bps,
    initial_equity_usdt: params.initial_equity,
    leverage: params.leverage ?? 1,
  };
  if (params.trade_amount_usdt != null && params.trade_amount_usdt > 0) {
    body.trade_amount_usdt = params.trade_amount_usdt;
  }
  if (params.start_time_ms != null && Number.isFinite(params.start_time_ms)) {
    body.start_time_ms = Math.floor(params.start_time_ms);
  }
  if (params.end_time_ms != null && Number.isFinite(params.end_time_ms)) {
    body.end_time_ms = Math.floor(params.end_time_ms);
  }

  const res = await fetch(`${apiPrefix()}/backtest/quick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`回测失败: ${res.status}`);
  const raw = (await res.json()) as Record<string, unknown>;
  return normalizeQuickBacktest(raw);
}

/** POST `/ai/verdict` 等职位的响应（与后端 `AiVerdictResponse` 对齐）。 */
function formatAiVerdictBody(data: Record<string, unknown>): string {
  const ok = data.success !== false;
  const src = String(data.source ?? "");
  const lines: string[] = [];
  if (src === "glm") lines.push("来源：智谱 GLM");
  else if (src === "heuristic_fallback") lines.push("来源：规则降级（未调用或不可用 GLM）");
  else if (src === "disabled") lines.push("来源：不可用");

  if (typeof data.bias === "string") {
    const c =
      typeof data.confidence === "number" && Number.isFinite(data.confidence)
        ? ` ${(data.confidence * 100).toFixed(0)}%`
        : "";
    lines.push(`结构倾向：${data.bias}${c}`);
  }

  const summary = typeof data.summary_zh === "string" ? data.summary_zh.trim() : "";
  if (summary) lines.push(summary);

  const reasons = Array.isArray(data.reasons_zh)
    ? data.reasons_zh.filter((x): x is string => typeof x === "string")
    : [];
  for (const r of reasons) lines.push(`• ${r}`);

  const ph = data.price_hints;
  if (ph && typeof ph === "object" && ph !== null) {
    const p = ph as Record<string, unknown>;
    const bits: string[] = [];
    if (typeof p.buy_focus_price === "number") bits.push(`买侧观察价 ${p.buy_focus_price}`);
    if (typeof p.sell_focus_price === "number") bits.push(`卖侧观察价 ${p.sell_focus_price}`);
    if (typeof p.stop_loss_buy === "number") bits.push(`多单止损参考 ${p.stop_loss_buy}`);
    if (typeof p.stop_loss_sell === "number") bits.push(`空单止损参考 ${p.stop_loss_sell}`);
    if (typeof p.note_zh === "string" && p.note_zh.trim()) bits.push(p.note_zh.trim());
    if (bits.length) lines.push(`参考价位：${bits.join("；")}`);
  }

  if (typeof data.error_detail === "string" && data.error_detail.trim()) {
    lines.push(`说明：${data.error_detail.trim()}`);
  }
  if (typeof data.model_name === "string" && data.model_name) {
    lines.push(`模型：${data.model_name}`);
  }
  if (typeof data.disclaimer === "string" && data.disclaimer && ok) {
    lines.push(`— ${data.disclaimer}`);
  }
  return lines.length ? lines.join("\n") : JSON.stringify(data);
}

export async function postVerdict(body: Record<string, unknown>, signal?: AbortSignal): Promise<string> {
  const endpoints = [
    `${apiPrefix()}/analyze/verdict`,
    `${apiPrefix()}/ai/verdict`,
    `${apiPrefix()}/api/ai/verdict`,
  ];
  for (const url of endpoints) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });
      if (res.ok) {
        const data = (await res.json()) as Record<string, unknown>;
        return formatAiVerdictBody(data);
      }
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      // Try next endpoint
    }
  }
  throw new Error("所有 verdict 端点均不可用");
}

export async function getSymbols(): Promise<SymbolOption[]> {
  try {
    const res = await fetch(`${apiPrefix()}/api/symbols`);
    if (!res.ok) return [];
    const data = (await res.json()) as Record<string, unknown> | unknown[];
    const rawList = Array.isArray(data)
      ? data
      : data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).symbols)
        ? ((data as Record<string, unknown>).symbols as unknown[])
        : [];
    const out: SymbolOption[] = [];
    for (const item of rawList) {
      if (typeof item === "string" && item.trim()) {
        out.push({ symbol: item.trim() });
        continue;
      }
      if (item && typeof item === "object" && typeof (item as SymbolOption).symbol === "string") {
        out.push(item as SymbolOption);
      }
    }
    return out;
  } catch {
    return [];
  }
}
