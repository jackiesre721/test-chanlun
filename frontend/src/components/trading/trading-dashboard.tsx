"use client";

import { useEffect } from "react";
import { useTradingStore } from "@/stores/trading-store";
import { AccountSummary } from "./account-summary";
import { PositionCard } from "./position-card";
import { PriceBar } from "./price-bar";

export function TradingDashboard() {
  const connected = useTradingStore((s) => s.connected);
  const positions = useTradingStore((s) => s.positions);
  const connect = useTradingStore((s) => s.connect);
  const disconnect = useTradingStore((s) => s.disconnect);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 px-1">
        <span
          className={`h-2 w-2 rounded-full ${connected ? "bg-positive" : "bg-negative"}`}
        />
        <span className="text-xs text-text-muted">
          {connected ? "实时连接" : "未连接"}
        </span>
      </div>
      <AccountSummary />
      <PriceBar />
      {positions.length === 0 ? (
        <div className="rounded-lg border border-border-subtle bg-bg-card/50 p-4 text-center text-sm text-text-muted">
          暂无持仓
        </div>
      ) : (
        positions.map((p) => <PositionCard key={p.position_id} position={p} />)
      )}
    </div>
  );
}
