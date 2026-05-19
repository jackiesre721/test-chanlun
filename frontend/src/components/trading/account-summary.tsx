import { useTradingStore } from "@/stores/trading-store";

function StatRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-text-muted">{label}</span>
      <span className={color ?? "text-text-primary"}>{value}</span>
    </div>
  );
}

function fmt(n: number): string {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function AccountSummary() {
  const account = useTradingStore((s) => s.account);

  if (!account) {
    return (
      <div className="rounded-lg border border-border-subtle bg-bg-card p-3">
        <div className="section-label">账户概览</div>
        <div className="text-xs text-text-muted">等待数据...</div>
      </div>
    );
  }

  const dailyPnlColor =
    account.daily_pnl > 0 ? "text-positive" : account.daily_pnl < 0 ? "text-negative" : "text-text-primary";

  return (
    <div className="rounded-lg border border-border-subtle bg-bg-card p-3">
      <div className="section-label">账户概览</div>
      <div className="space-y-1.5">
        <StatRow label="初始净值" value={`$${fmt(account.initial_equity)}`} />
        <StatRow label="当前净值" value={`$${fmt(account.current_equity)}`} />
        <StatRow
          label="日内盈亏"
          value={`${account.daily_pnl >= 0 ? "+" : ""}$${fmt(account.daily_pnl)}`}
          color={dailyPnlColor}
        />
        <StatRow label="可用余额" value={`$${fmt(account.available_balance)}`} />
        <StatRow label="未实现盈亏" value={`$${fmt(account.unrealized_pnl)}`} />
        <StatRow label="持仓数量" value={String(account.open_positions)} />
      </div>
    </div>
  );
}
