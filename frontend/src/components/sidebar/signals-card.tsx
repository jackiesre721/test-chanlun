import { Card, CardHeader, CardContent, Chip } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useRiskStore } from "@/stores/risk-store";
import { fmtOpenTime } from "@/lib/format";
import { KIND_NAME } from "@/constants/label-maps";

function rrClass(rr: number | null | undefined) {
  if (rr == null) return "";
  if (rr >= 2) return "text-success";
  if (rr >= 1.5) return "text-warning";
  return "text-negative";
}

export function SignalCard({ signal, onNavigate }: { signal: any; onNavigate?: (idx: number) => void }) {
  const fillRisk = useRiskStore((s) => s.fillFromSignal);
  const isBuy = signal.side === "BUY";

  return (
    <div
      className="p-2.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] cursor-pointer transition-colors border border-transparent hover:border-border-subtle"
      onClick={() => onNavigate?.(signal.idx)}
    >
      <div className="flex items-center gap-2 mb-1">
        <Chip size="sm" variant="flat" color={isBuy ? "success" : "danger"}>
          {signal.side}
        </Chip>
        <span className="text-[11px] text-text-muted">
          {KIND_NAME[signal.kind] || signal.kind}
        </span>
        <span className="text-xs font-mono ml-auto">{Number(signal.price).toFixed(2)}</span>
      </div>
      {signal.open_time && (
        <div className="text-[10px] text-text-muted mb-1">{fmtOpenTime(signal.open_time)}</div>
      )}
      {signal.description && (
        <div className="text-[11px] text-text-primary/70 mb-1">{signal.description}</div>
      )}
      {signal.evidence && (
        <div className="text-[10px] text-text-muted mb-1">{signal.evidence}</div>
      )}
      {signal.stop_loss != null && signal.take_profit != null && (
        <div className={`mt-1.5 p-1.5 rounded bg-white/[0.03] text-[11px] flex items-center gap-3 ${rrClass(signal.risk_reward_ratio)}`}>
          <span>SL: {Number(signal.stop_loss).toFixed(2)}</span>
          <span>TP: {Number(signal.take_profit).toFixed(2)}</span>
          {signal.risk_reward_ratio != null && <span className="font-bold">R:R {signal.risk_reward_ratio.toFixed(1)}</span>}
        </div>
      )}
      {signal.stop_loss != null && (
        <button
          className="mt-1.5 text-[10px] px-2 py-0.5 rounded bg-accent/15 text-accent hover:bg-accent/25 transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            fillRisk(signal.price, signal.stop_loss);
          }}
        >
          填入风控试算
        </button>
      )}
    </div>
  );
}

export function SignalsCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);

  const allSignals = lastResult
    ? [...(lastResult.buy_signals || []), ...(lastResult.sell_signals || [])].sort((a, b) => b.idx - a.idx)
    : [];

  const handleNavigate = (idx: number) => {
    (window as any).__chanlan_navigateToSignal?.(idx);
  };

  return (
    <Card className="bg-bg-card border border-border-subtle">
      <CardHeader className="font-bold text-sm px-3 py-2">买卖点信号</CardHeader>
      <CardContent className="px-3 pb-3">
        {error ? (
          <span className="text-xs text-negative">暂无信号</span>
        ) : !lastResult ? (
          <span className="text-xs text-text-muted">分析后列出买卖点信号、止损/止盈与 R:R 比值。</span>
        ) : allSignals.length === 0 ? (
          <span className="text-xs text-text-muted">当前列表为空：多为结构不足以程序判定买卖点。</span>
        ) : (
          <div className="space-y-2">
            <div className="text-[10px] text-text-muted">默认展示最近信号，点击可导航到图表。</div>
            {allSignals.slice(0, 4).map((s, i) => (
              <SignalCard key={i} signal={s} onNavigate={handleNavigate} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
