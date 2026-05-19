"use client";

import { useState } from "react";
import type { Position } from "@/stores/trading-store";
import { useTradingStore } from "@/stores/trading-store";
import { closePosition } from "@/lib/api";

function fmt(n: number): string {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtQty(qty: number): string {
  if (qty >= 1000) return qty.toFixed(1);
  if (qty >= 1) return qty.toFixed(2);
  if (qty >= 0.01) return qty.toFixed(4);
  return qty.toFixed(6);
}

function calcUnrealizedPnl(position: Position, currentPrice: number): number {
  if (position.side.toUpperCase() === "LONG") {
    return (currentPrice - position.entry_price) * position.quantity;
  }
  return (position.entry_price - currentPrice) * position.quantity;
}

function calcRMultiple(position: Position, currentPrice: number): number {
  const risk = Math.abs(position.entry_price - position.stop_loss);
  if (risk === 0) return 0;
  if (position.side.toUpperCase() === "LONG") {
    return (currentPrice - position.entry_price) / risk;
  }
  return (position.entry_price - currentPrice) / risk;
}

function parseReductions(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.map(String);
    return [];
  } catch {
    return [];
  }
}

export function PositionCard({ position }: { position: Position }) {
  const prices = useTradingStore((s) => s.prices);
  const [closing, setClosing] = useState(false);

  const currentPrice = prices[position.symbol] ?? 0;
  const hasPrice = currentPrice > 0;

  const unrealizedPnl = hasPrice ? calcUnrealizedPnl(position, currentPrice) : 0;
  const rMultiple = hasPrice ? calcRMultiple(position, currentPrice) : 0;

  const isLong = position.side.toUpperCase() === "LONG";
  const sideColor = isLong ? "text-positive" : "text-negative";
  const sideBg = isLong ? "bg-positive/10" : "bg-negative/10";

  const pnlColor =
    unrealizedPnl > 0 ? "text-positive" : unrealizedPnl < 0 ? "text-negative" : "text-text-primary";

  const rColor =
    rMultiple > 0 ? "text-positive" : rMultiple < 0 ? "text-negative" : "text-text-muted";

  const reductions = parseReductions(position.reductions_done);

  const handleClose = async () => {
    if (closing || !hasPrice) return;
    setClosing(true);
    try {
      await closePosition(position.position_id, currentPrice);
    } catch (err) {
      console.error("[trading] close failed", err);
    } finally {
      setClosing(false);
    }
  };

  return (
    <div className="rounded-lg border border-border-subtle bg-bg-card p-3 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary">{position.symbol}</span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${sideColor} ${sideBg}`}>
            {position.side.toUpperCase()}
          </span>
          <span className="rounded bg-bg-deep px-1.5 py-0.5 text-[10px] text-text-muted">
            {position.leverage}x
          </span>
        </div>
        <span className="text-[10px] text-text-muted">{position.signal_kind ?? ""}</span>
      </div>

      {/* Price rows */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-text-muted">入场</span>
          <span className="text-text-primary tabular-nums">{fmt(position.entry_price)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">现价</span>
          <span className="text-text-primary tabular-nums">{hasPrice ? fmt(currentPrice) : "—"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">止损</span>
          <span className="text-negative tabular-nums">{fmt(position.stop_loss)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">止盈1</span>
          <span className="text-positive tabular-nums">{position.take_profit_1 ? fmt(position.take_profit_1) : "—"}</span>
        </div>
        {position.take_profit_2 != null && (
          <div className="flex justify-between">
            <span className="text-text-muted">止盈2</span>
            <span className="text-positive tabular-nums">{fmt(position.take_profit_2!)}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-text-muted">数量</span>
          <span className="text-text-primary tabular-nums">{fmtQty(position.quantity)}</span>
        </div>
      </div>

      {/* PnL & R-multiple */}
      <div className="flex items-center justify-between border-t border-border-subtle pt-2 text-xs">
        <div>
          <span className="text-text-muted">未实现盈亏 </span>
          <span className={`font-semibold tabular-nums ${pnlColor}`}>
            {unrealizedPnl >= 0 ? "+" : ""}{fmt(unrealizedPnl)}
          </span>
        </div>
        <div>
          <span className="text-text-muted">R </span>
          <span className={`font-semibold tabular-nums ${rColor}`}>
            {rMultiple >= 0 ? "+" : ""}{rMultiple.toFixed(2)}R
          </span>
        </div>
      </div>

      {/* Trailing stop indicator */}
      {position.trailing_stop != null && (
        <div className="text-xs text-text-muted">
          移动止损: <span className="text-text-primary tabular-nums">{fmt(position.trailing_stop)}</span>
        </div>
      )}

      {/* Reductions */}
      {reductions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {reductions.map((r, i) => (
            <span key={i} className="rounded bg-bg-deep px-1.5 py-0.5 text-[10px] text-text-muted">
              {r}
            </span>
          ))}
        </div>
      )}

      {/* Close button */}
      {hasPrice && (
        <button
          type="button"
          onClick={handleClose}
          disabled={closing}
          className="w-full rounded-md border border-negative/30 bg-negative/5 px-3 py-1.5 text-xs font-medium text-negative transition-colors hover:bg-negative/10 disabled:opacity-50"
        >
          {closing ? "平仓中..." : "平仓"}
        </button>
      )}
    </div>
  );
}
