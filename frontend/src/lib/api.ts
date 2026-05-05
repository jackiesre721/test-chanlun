import type {
  AnalyzeResult,
  PositionSizeRequest,
  PositionSizeResponse,
  PaperTradeRequest,
  PaperTradeRecord,
  BacktestRequest,
  BacktestResult,
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
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`风控计算失败: ${res.status}`);
  return res.json();
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

export async function postBacktestQuick(params: BacktestRequest): Promise<BacktestResult> {
  const res = await fetch(`${apiPrefix()}/backtest/quick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`回测失败: ${res.status}`);
  return res.json();
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
