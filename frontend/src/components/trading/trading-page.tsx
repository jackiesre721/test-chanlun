import { useEffect } from "react";
import { useTradingStore } from "@/stores/trading-store";
import { useSettingsStore } from "@/stores/settings-store";
import { AccountSummary } from "./account-summary";
import { PositionCard } from "./position-card";
import { PriceBar } from "./price-bar";
import { TradeJournal } from "./trade-journal";

export function TradingPage() {
  const connected = useTradingStore((s) => s.connected);
  const positions = useTradingStore((s) => s.positions);
  const prices = useTradingStore((s) => s.prices);
  const connect = useTradingStore((s) => s.connect);
  const disconnect = useTradingStore((s) => s.disconnect);
  const setViewMode = useSettingsStore((s) => s.setViewMode);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  const longPositions = positions.filter((p) => p.side === "LONG");
  const shortPositions = positions.filter((p) => p.side === "SHORT");
  const totalUnrealized = positions.reduce((sum, p) => {
    const currentPrice = prices[p.symbol] ?? p.entry_price;
    const diff = p.side === "LONG"
      ? currentPrice - p.entry_price
      : p.entry_price - currentPrice;
    return sum + diff * p.quantity;
  }, 0);

  return (
    <div className="flex h-full flex-col bg-bg-deep">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle bg-bg-card/80 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setViewMode("chart")}
            className="rounded px-2 py-1 text-xs text-text-muted hover:bg-bg-deep hover:text-text-primary transition-colors"
          >
            ← 返回图表
          </button>
          <h1 className="text-sm font-semibold text-text-primary">实时交易</h1>
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-positive" : "bg-negative"}`} />
          <span className="text-xs text-text-muted">{connected ? "已连接" : "未连接"}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className={`text-sm font-medium ${totalUnrealized >= 0 ? "text-positive" : "text-negative"}`}>
            未实现: {totalUnrealized >= 0 ? "+" : ""}{totalUnrealized.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Price bar */}
      <div className="border-b border-border-subtle bg-bg-card/40 px-4 py-2">
        <PriceBar />
      </div>

      {/* Main content */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: Account + Positions */}
        <div className="flex-1 min-w-0 overflow-y-auto p-4 space-y-4">
          <AccountSummary />

          {/* Position summary bar */}
          <div className="flex gap-3 text-xs">
            <span className="rounded bg-bg-card/60 px-2 py-1 text-text-muted">
              持仓 <span className="text-text-primary font-medium">{positions.length}</span>
            </span>
            <span className="rounded bg-positive/10 px-2 py-1 text-positive">
              多 {longPositions.length}
            </span>
            <span className="rounded bg-negative/10 px-2 py-1 text-negative">
              空 {shortPositions.length}
            </span>
          </div>

          {/* Positions grid */}
          {positions.length === 0 ? (
            <div className="rounded-lg border border-border-subtle bg-bg-card/50 p-8 text-center text-sm text-text-muted">
              暂无持仓
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              {positions.map((p) => (
                <PositionCard key={p.position_id} position={p} />
              ))}
            </div>
          )}
        </div>

        {/* Right: Trade journal */}
        <div className="w-[min(35vw,400px)] min-w-[300px] border-l border-border-subtle overflow-y-auto p-4">
          <TradeJournal />
        </div>
      </div>
    </div>
  );
}
