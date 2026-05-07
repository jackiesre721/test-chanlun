import { Card, CardContent } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useRiskStore } from "@/stores/risk-store";
import { fmtOpenTime, fmtPrice, fmtRR } from "@/lib/format";
import { KIND_NAME } from "@/constants/label-maps";

const KIND_COLOR: Record<string, string> = {
  first: "text-warning",
  second: "text-accent",
  second_extend: "text-accent/70",
  third: "text-positive",
  second_class: "text-warning/80",
  third_class: "text-positive/70",
  td9: "text-text-muted",
};

function rrClass(rr: number | null | undefined) {
  if (rr == null) return "";
  if (rr >= 2) return "text-success";
  if (rr >= 1.5) return "text-warning";
  return "text-negative";
}

interface SignalLike {
  idx: number;
  side: string;
  kind: string;
  price: number;
  stop_loss?: number | null;
  stop_loss_2?: number | null;
  take_profit_1?: number | null;
  take_profit?: number | null;
  risk_reward_ratio?: number | null;
  open_time?: number | null;
}

function mergeSignals(signals: SignalLike[]): (SignalLike & { count: number })[] {
  const groups: Map<string, { signal: SignalLike; count: number }> = new Map();
  for (const s of signals) {
    const sl = s.stop_loss != null ? Number(s.stop_loss).toFixed(2) : "null";
    const key = `${s.side}-${s.kind}-${Number(s.price).toFixed(2)}-${sl}`;
    const existing = groups.get(key);
    if (existing) {
      existing.count++;
    } else {
      groups.set(key, { signal: s, count: 1 });
    }
  }
  return [...groups.values()].sort((a, b) => b.signal.idx - a.signal.idx).map((g) => ({
    ...g.signal,
    count: g.count,
  }));
}

export function SignalCard({
  signal,
  count,
  onNavigate,
}: {
  signal: SignalLike;
  count?: number;
  onNavigate?: (idx: number) => void;
}) {
  const fillRisk = useRiskStore((s) => s.fillFromSignal);
  const isBuy = signal.side === "BUY";
  const borderColor = isBuy ? "border-l-positive" : "border-l-negative";
  const pillBg = isBuy ? "bg-positive/15 text-positive" : "bg-negative/15 text-negative";
  const kindColor = KIND_COLOR[signal.kind] || "text-text-primary/90";

  return (
    <div
      className={`signal-row group border-l-2 ${borderColor}`}
      onClick={() => onNavigate?.(signal.idx)}
    >
      <div className="flex flex-col items-center gap-1 shrink-0">
        <span
          className={`text-[10px] font-bold px-1.5 py-0.5 rounded-sm num tracking-wide ${pillBg}`}
        >
          {signal.side === "BUY" ? "▲ BUY" : "▼ SELL"}
        </span>
        {count != null && count > 1 && (
          <span className="text-[9px] text-text-muted num">+{count - 1}</span>
        )}
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={`text-[11px] font-medium truncate ${kindColor}`}>
            {KIND_NAME[signal.kind] || signal.kind}
          </span>
          {signal.open_time && (
            <span className="text-[10px] text-text-muted">{fmtOpenTime(signal.open_time)}</span>
          )}
        </div>
        {(signal.stop_loss != null ||
          signal.stop_loss_2 != null ||
          signal.take_profit_1 != null ||
          signal.take_profit != null) && (
          <div
            className={`mt-1 text-[10px] flex flex-wrap gap-x-3 gap-y-0.5 num ${rrClass(signal.risk_reward_ratio)}`}
          >
            {signal.stop_loss != null && (
              <span className="text-warning">SL {fmtPrice(signal.stop_loss)}</span>
            )}
            {signal.stop_loss_2 != null && (
              <span className="text-warning/90">SL₂ {fmtPrice(signal.stop_loss_2)}</span>
            )}
            {signal.take_profit_1 != null && (
              <span className="text-success">TP1 {fmtPrice(signal.take_profit_1)}</span>
            )}
            {signal.take_profit != null && (
              <span className="text-success">TP2 {fmtPrice(signal.take_profit)}</span>
            )}
            {signal.risk_reward_ratio != null && (
              <span className="font-bold">R:R {fmtRR(signal.risk_reward_ratio)}</span>
            )}
          </div>
        )}
      </div>
      <div className="text-right shrink-0">
        <div className="text-xs font-mono font-medium num">{fmtPrice(signal.price)}</div>
        {signal.stop_loss != null && (
          <button
            className="text-[9px] mt-0.5 px-1.5 py-px rounded bg-surface-accent text-accent hover:bg-surface-active transition-colors opacity-0 group-hover:opacity-100"
            onClick={(e) => {
              e.stopPropagation();
              fillRisk(signal.price, signal.stop_loss!);
            }}
          >
            风控
          </button>
        )}
      </div>
    </div>
  );
}

export function SignalsCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);

  const allSignals: SignalLike[] = lastResult
    ? [...(lastResult.buy_signals || []), ...(lastResult.sell_signals || [])].sort((a, b) => b.idx - a.idx)
    : [];

  const merged = mergeSignals(allSignals);

  const handleNavigate = (idx: number) => {
    (window as any).__chanlan_navigateToSignal?.(idx);
  };

  return (
    <Card className="card-glow bg-bg-card border border-border-subtle">
      <div className="section-label">买卖点信号</div>
      <CardContent className="px-3 pb-3">
        {error ? (
          <span className="text-xs text-negative">暂无信号</span>
        ) : !lastResult ? (
          <span className="text-xs text-text-muted">分析后列出买卖点信号、止损/止盈与 R:R 比值。</span>
        ) : allSignals.length === 0 ? (
          <span className="text-xs text-text-muted">当前列表为空：多为结构不足以程序判定买卖点。</span>
        ) : (
          <div className="space-y-1.5">
            <div className="text-[10px] text-text-muted mb-1">点击信号可导航到图表对应位置</div>
            {merged.slice(0, 8).map((s, i) => (
              <SignalCard key={`${s.side}-${s.kind}-${s.idx}`} signal={s} count={s.count} onNavigate={handleNavigate} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
