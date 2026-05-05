"""演示级快速回测：全样本跑一次缠论流水线 + 极简成交模型（非业绩承诺）。"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Literal, Optional, Tuple

from app.core.config import settings
from app.core.models import (
    Candle,
    QuickBacktestKindStat,
    QuickBacktestMetrics,
    QuickBacktestRequest,
    QuickBacktestResponse,
    QuickBacktestRoundTrip,
    QuickBacktestTrade,
    Signal,
    SignalSide,
)
from app.repositories.market_data import BinanceRepository
from app.services.analysis_pipeline import build_analyze_bundle


def _mark_equity_usdt(cash: float, btc_qty: float, px: float) -> float:
    return cash + btc_qty * px


@dataclass
class _PendingOpen:
    equity_before: float
    bar_idx: int
    time: str
    price: float
    kind: str
    side: Literal["LONG", "SHORT"]


def _aggregate_round_trips(
    round_trips: list[QuickBacktestRoundTrip],
) -> tuple[
    dict[str, QuickBacktestKindStat],
    float,
    Optional[float],
    Optional[float],
    int,
    Optional[float],
    Optional[float],
]:
    """返回 stats_by_kind, win_rate, profit_factor, expectancy, max_cons_losses, avg_win, avg_loss。"""
    if not round_trips:
        return {}, None, None, None, 0, None, None

    pnls = [r.pnl_usdt for r in round_trips]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    losses_n = sum(1 for p in pnls if p < 0)
    win_rate = wins / n

    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = sum(-p for p in pnls if p < 0)
    profit_factor = (gross_win / gross_loss) if gross_loss > 1e-12 else None
    expectancy = float(mean(pnls))

    max_cons = cur = 0
    for p in pnls:
        if p < 0:
            cur += 1
            max_cons = max(max_cons, cur)
        else:
            cur = 0

    avg_win = float(mean([p for p in pnls if p > 0])) if wins else None
    avg_loss = float(mean([p for p in pnls if p < 0])) if losses_n else None

    by_kind: dict[str, list[float]] = defaultdict(list)
    for r in round_trips:
        by_kind[r.signal_kind_at_entry].append(r.pnl_usdt)

    stats_models: dict[str, QuickBacktestKindStat] = {}
    for k, lst in by_kind.items():
        wk = sum(1 for x in lst if x > 0)
        lk = sum(1 for x in lst if x < 0)
        stats_models[k] = QuickBacktestKindStat(
            count=len(lst),
            wins=wk,
            losses=lk,
            win_rate=(wk / len(lst)) if lst else 0.0,
            avg_pnl_usdt=float(mean(lst)),
        )

    return stats_models, win_rate, profit_factor, expectancy, max_cons, avg_win, avg_loss


def _simulate(
    candles: list[Candle],
    *,
    strategy: str,
    fee_bps: float,
    initial_equity_usdt: float,
    buy_signals: list[Signal],
    sell_signals: list[Signal],
) -> Tuple[list[QuickBacktestTrade], list[QuickBacktestRoundTrip], float, float]:
    fee_rate = fee_bps / 10_000
    cash = float(initial_equity_usdt)
    btc_qty = 0.0

    signals = sorted(
        buy_signals + sell_signals,
        key=lambda s: (s.idx, 0 if s.side == SignalSide.BUY else 1),
    )

    trades: list[QuickBacktestTrade] = []
    round_trips: list[QuickBacktestRoundTrip] = []
    peak_equity = float(initial_equity_usdt)
    max_dd = 0.0
    pending: Optional[_PendingOpen] = None

    def equity_at(px: float) -> float:
        return _mark_equity_usdt(cash, btc_qty, px)

    def bump_dd(px: float) -> None:
        nonlocal peak_equity, max_dd
        eq = equity_at(px)
        peak_equity = max(peak_equity, eq)
        if peak_equity > 0:
            max_dd = max(max_dd, (peak_equity - eq) / peak_equity)

    def finalize_round(po: _PendingOpen, exit_bar: int, exit_time: str, exit_px: float, eq_after: float) -> None:
        pnl = eq_after - po.equity_before
        pct = (pnl / po.equity_before * 100.0) if po.equity_before > 1e-12 else 0.0
        round_trips.append(
            QuickBacktestRoundTrip(
                entry_bar_idx=po.bar_idx,
                exit_bar_idx=exit_bar,
                entry_time=po.time,
                exit_time=exit_time,
                entry_price=po.price,
                exit_price=float(exit_px),
                side=po.side,
                pnl_usdt=float(pnl),
                pnl_pct=float(pct),
                bars_held=max(0, exit_bar - po.bar_idx),
                signal_kind_at_entry=po.kind,
            )
        )

    action: str

    for sig in signals:
        px = candles[sig.idx].close if sig.idx < len(candles) else candles[-1].close
        time_str = candles[sig.idx].time if sig.idx < len(candles) else candles[-1].time

        if sig.side == SignalSide.BUY:
            if btc_qty > 0:
                continue
            if btc_qty < 0:
                qty_cover = abs(btc_qty)
                cash -= qty_cover * px * (1 + fee_rate)
                btc_qty = 0.0
                eq_cov = equity_at(px)
                if pending is not None and pending.side == "SHORT":
                    finalize_round(pending, sig.idx, time_str, px, eq_cov)
                pending = None
            if cash <= 0:
                continue
            eq_before_open = equity_at(px)
            pending = _PendingOpen(
                equity_before=eq_before_open,
                bar_idx=sig.idx,
                time=time_str,
                price=float(px),
                kind=sig.kind,
                side="LONG",
            )
            qty_long = cash / (px * (1 + fee_rate))
            btc_qty += qty_long
            cash = 0.0
            action = "BUY"
        else:
            if strategy == "long_only_flip":
                if btc_qty <= 0:
                    continue
                qty = btc_qty
                cash += qty * px * (1 - fee_rate)
                btc_qty = 0.0
                action = "SELL"
                eq = equity_at(px)
                if pending is not None and pending.side == "LONG":
                    finalize_round(pending, sig.idx, time_str, px, eq)
                pending = None
            else:
                if btc_qty > 0:
                    qty = btc_qty
                    cash += qty * px * (1 - fee_rate)
                    btc_qty = 0.0
                    action = "SELL"
                    eq = equity_at(px)
                    if pending is not None and pending.side == "LONG":
                        finalize_round(pending, sig.idx, time_str, px, eq)
                    pending = None
                elif btc_qty == 0:
                    if cash <= 0:
                        continue
                    eq_before_open = equity_at(px)
                    pending = _PendingOpen(
                        equity_before=eq_before_open,
                        bar_idx=sig.idx,
                        time=time_str,
                        price=float(px),
                        kind=sig.kind,
                        side="SHORT",
                    )
                    qty_short = cash / (px * (1 + fee_rate))
                    btc_qty -= qty_short
                    cash += qty_short * px * (1 - fee_rate)
                    action = "SELL"
                else:
                    continue

        eq = equity_at(px)
        bump_dd(px)

        trades.append(
            QuickBacktestTrade(
                bar_idx=sig.idx,
                time=time_str,
                action=action,
                price=float(px),
                equity_after=float(eq),
            )
        )

    last_px = candles[-1].close
    final_eq = equity_at(last_px)
    peak_equity = max(peak_equity, final_eq)
    if peak_equity > 0:
        max_dd = max(max_dd, (peak_equity - final_eq) / peak_equity)

    return trades, round_trips, float(final_eq), float(max_dd)


def _naive_sharpe(trades: list[QuickBacktestTrade]) -> Optional[float]:
    if len(trades) < 3:
        return None
    rets: list[float] = []
    for prev, nxt in zip(trades, trades[1:]):
        if prev.equity_after <= 0:
            continue
        rets.append(nxt.equity_after / prev.equity_after - 1.0)
    if len(rets) < 2:
        return None
    std = pstdev(rets)
    if std <= 1e-12:
        return None
    return (mean(rets) / std) * math.sqrt(len(rets))


async def run_quick_backtest(repository: BinanceRepository, request: QuickBacktestRequest) -> QuickBacktestResponse:
    cap = min(request.max_bars, settings.backtest_max_bars)
    candles = await repository.get_klines_history(request.symbol, request.interval, cap)
    bundle = build_analyze_bundle(
        candles,
        market=request.market,
        symbol=request.symbol,
        interval=request.interval,
        higher_strokes=[],
        higher_pivots=[],
        warning_override=None,
        higher_interval=None,
    )

    trades, round_trips, final_eq, max_dd = _simulate(
        candles,
        strategy=request.strategy,
        fee_bps=request.fee_bps,
        initial_equity_usdt=request.initial_equity_usdt,
        buy_signals=bundle.all_buy_signals,
        sell_signals=bundle.all_sell_signals,
    )

    total_ret = (final_eq / request.initial_equity_usdt) - 1.0 if request.initial_equity_usdt > 0 else 0.0
    sharpe = _naive_sharpe(trades)

    stats_by_kind, win_rate, profit_factor, expectancy, max_cons, avg_win, avg_loss = _aggregate_round_trips(round_trips)

    metrics = QuickBacktestMetrics(
        bars_used=len(candles),
        trades=len(trades),
        final_equity_usdt=final_eq,
        total_return_fraction=float(total_ret),
        max_drawdown_fraction=float(max_dd),
        sharpe_naive=sharpe,
        closed_trade_count=len(round_trips),
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy_per_trade_usdt=expectancy,
        max_consecutive_losses=max_cons,
        avg_win_usdt=avg_win,
        avg_loss_usdt=avg_loss,
    )

    return QuickBacktestResponse(
        metrics=metrics,
        trade_log=trades,
        closed_trades=round_trips,
        stats_by_signal_kind=stats_by_kind,
    )
