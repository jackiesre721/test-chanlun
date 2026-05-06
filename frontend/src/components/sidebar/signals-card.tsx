import { Card, CardContent, Chip } from "@heroui/react";
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
      className="signal-row group"
      onClick={() => onNavigate?.(signal.idx)}
    >
      <Chip size="sm" variant="soft" color={isBuy ? "success" : "danger"} className="shrink-0">
        {signal.side}
      </Chip>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-text-primary/90 font-medium truncate">
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
              <span className="text-warning">SL {Number(signal.stop_loss).toFixed(2)}</span>
            )}
            {signal.stop_loss_2 != null && (
              <span className="text-warning/90">SL₂ {Number(signal.stop_loss_2).toFixed(2)}</span>
            )}
            {signal.take_profit_1 != null && (
              <span className="text-success">TP1 {Number(signal.take_profit_1).toFixed(2)}</span>
            )}
            {signal.take_profit != null && (
              <span className="text-success">TP2 {Number(signal.take_profit).toFixed(2)}</span>
            )}
            {signal.risk_reward_ratio != null && (
              <span className="font-bold">R:R {signal.risk_reward_ratio.toFixed(1)}</span>
            )}
          </div>
        )}
      </div>
      <div className="text-right shrink-0">
        <div className="text-xs font-mono font-medium num">{Number(signal.price).toFixed(2)}</div>
        {signal.stop_loss != null && (
          <button
            className="text-[9px] mt-0.5 px-1.5 py-px rounded bg-surface-accent text-accent hover:bg-surface-active transition-colors opacity-0 group-hover:opacity-100"
            onClick={(e) => {
              e.stopPropagation();
              fillRisk(signal.price, signal.stop_loss);
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

  const allSignals = lastResult
    ? [...(lastResult.buy_signals || []), ...(lastResult.sell_signals || [])].sort((a, b) => b.idx - a.idx)
    : [];

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
            {allSignals.slice(0, 4).map((s, i) => (
              <SignalCard key={i} signal={s} onNavigate={handleNavigate} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
