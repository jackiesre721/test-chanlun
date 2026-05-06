"""演示级快速回测：全样本跑一次缠论流水线 + 信号驱动成交模型（非业绩承诺）。"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Literal, Optional, Tuple

from app.core.config import settings
from app.core.models import (
    Candle,
    Pivot,
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
from app.services.analyzer import HIGHER_INTERVAL, project_higher_onto_base
from app.services.analysis_pipeline import build_analyze_bundle

# ── Phase 1 strategy parameters ──

# Signal kinds to skip entirely
_SKIP_KINDS: frozenset[str] = frozenset({"first", "third_class"})

# Signal kinds that use half margin
_HALF_MARGIN_KINDS: frozenset[str] = frozenset({"second_extend", "second_class"})


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
    Optional[float],
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
    leverage: int = 1,
    buy_signals: list[Signal],
    sell_signals: list[Signal],
    trade_amount_usdt: float | None = None,
) -> Tuple[list[QuickBacktestTrade], list[QuickBacktestRoundTrip], float, float]:
    """可选固定每笔保证金；含信号止损与杠杆强平；附带回合平仓统计。"""
    fee_rate = fee_bps / 10_000
    lev = float(leverage)
    fixed_margin = float(trade_amount_usdt) if trade_amount_usdt else None

    signals = sorted(
        buy_signals + sell_signals,
        key=lambda s: (s.idx, 0 if s.side == SignalSide.BUY else 1),
    )
    sig_map: dict[int, list[Signal]] = {}
    for sig in signals:
        sig_map.setdefault(sig.idx, []).append(sig)

    trades: list[QuickBacktestTrade] = []
    round_trips: list[QuickBacktestRoundTrip] = []
    peak_equity = float(initial_equity_usdt)
    max_dd = 0.0

    pos_qty: float = 0.0
    pos_entry: float = 0.0
    pos_margin: float = 0.0
    active_sl: float | None = None
    balance: float = float(initial_equity_usdt)
    pending: Optional[_PendingOpen] = None

    def _unrealized(px: float) -> float:
        if pos_qty > 0:
            return pos_qty * (px - pos_entry)
        if pos_qty < 0:
            return abs(pos_qty) * (pos_entry - px)
        return 0.0

    def _equity(px: float) -> float:
        return balance + _unrealized(px)

    def _update_peak_dd(eq: float) -> None:
        nonlocal peak_equity, max_dd
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

    def _close(bar_idx: int, time_str: str, close_px: float, reason: str) -> None:
        nonlocal balance, pos_qty, pos_entry, pos_margin, active_sl, pending

        closed_side: Literal["LONG", "SHORT"] = "LONG" if pos_qty > 0 else "SHORT"

        if pos_qty > 0:
            pnl = pos_qty * close_px * (1 - fee_rate) - pos_qty * pos_entry
        else:
            pnl = (
                abs(pos_qty) * pos_entry * (1 - fee_rate)
                - abs(pos_qty) * close_px * (1 + fee_rate)
            )
        pnl = max(-pos_margin, pnl)
        balance += pnl
        if balance < 0:
            balance = 0.0
        eq_flat = balance

        if pending is not None and pending.side == closed_side:
            finalize_round(pending, bar_idx, time_str, float(close_px), float(eq_flat))
            pending = None

        action = "SELL" if closed_side == "LONG" else "BUY"
        _update_peak_dd(eq_flat)
        trades.append(
            QuickBacktestTrade(
                bar_idx=bar_idx,
                time=time_str,
                action=action,
                price=float(close_px),
                equity_after=float(eq_flat),
                exit_reason=reason,
                quantity=abs(pos_qty),
            )
        )
        pos_qty = 0.0
        pos_entry = 0.0
        pos_margin = 0.0
        active_sl = None

    def _open(sig: Signal, px: float, candle: Candle, side: str) -> None:
        nonlocal pos_qty, pos_entry, pos_margin, active_sl, pending
        margin = min(fixed_margin, balance) if fixed_margin else balance
        # Phase 1: half margin for lower-confidence signal kinds
        if sig.kind in _HALF_MARGIN_KINDS:
            margin *= 0.5
        if margin <= 0:
            return
        equity_before_open = _equity(px)
        qty = margin * lev / (px * (1 + fee_rate))
        pos_qty = qty if side == "BUY" else -qty
        pos_entry = px
        pos_margin = margin
        active_sl = sig.stop_loss
        pending = _PendingOpen(
            equity_before=float(equity_before_open),
            bar_idx=sig.idx,
            time=candle.time,
            price=float(px),
            kind=sig.kind,
            side="LONG" if side == "BUY" else "SHORT",
        )
        eq = _equity(px)
        _update_peak_dd(eq)
        trades.append(
            QuickBacktestTrade(
                bar_idx=sig.idx,
                time=candle.time,
                action=side,
                price=float(px),
                equity_after=float(eq),
                exit_reason="signal",
                quantity=abs(pos_qty),
                stop_loss=sig.stop_loss,
                take_profit_1=sig.take_profit_1,
                take_profit_2=sig.take_profit,
            )
        )

    for bar_idx, candle in enumerate(candles):
        if pos_qty != 0 and active_sl is not None:
            sl_hit = False
            if pos_qty > 0 and candle.low <= active_sl:
                _close(bar_idx, candle.time, active_sl, "stop_loss")
                sl_hit = True
            elif pos_qty < 0 and candle.high >= active_sl:
                _close(bar_idx, candle.time, active_sl, "stop_loss")
                sl_hit = True
            if sl_hit:
                continue

        if pos_qty != 0 and lev > 1:
            liq_hit = False
            if pos_qty > 0:
                liq_px = pos_entry * (1 - 1 / lev)
                if candle.low <= liq_px:
                    _close(bar_idx, candle.time, liq_px, "liquidation")
                    liq_hit = True
            else:
                liq_px = pos_entry * (1 + 1 / lev)
                if candle.high >= liq_px:
                    _close(bar_idx, candle.time, liq_px, "liquidation")
                    liq_hit = True
            if liq_hit:
                continue

        if bar_idx not in sig_map:
            continue
        for sig in sig_map[bar_idx]:
            px = sig.price if sig.price else candle.close

            if sig.side == SignalSide.BUY:
                if pos_qty > 0:
                    continue
                if pos_qty < 0:
                    _close(bar_idx, candle.time, px, "signal")
                _open(sig, px, candle, "BUY")
            else:
                if pos_qty < 0:
                    continue
                if pos_qty > 0:
                    _close(bar_idx, candle.time, px, "signal")
                    continue
                if strategy == "long_only_flip":
                    continue
                _open(sig, px, candle, "SELL")

    final_eq = _equity(candles[-1].close)
    _update_peak_dd(final_eq)
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


def _apply_resonance_filter(
    buy_signals: list[Signal],
    sell_signals: list[Signal],
    composite: Optional[str],
) -> tuple[list[Signal], list[Signal]]:
    """Multi-timeframe resonance: only keep signals aligned with higher-level trend."""
    if not composite or composite in ("insufficient_higher_data", "aligned_consolidation", "partially_aligned"):
        return buy_signals, sell_signals
    if composite == "aligned_uptrend":
        return buy_signals, [s for s in sell_signals if s.kind == "first"]
    if composite == "aligned_downtrend":
        return [s for s in buy_signals if s.kind == "first"], sell_signals
    if composite == "cross_level_divergent":
        return (
            [s for s in buy_signals if s.kind == "first"],
            [s for s in sell_signals if s.kind == "first"],
        )
    return buy_signals, sell_signals


def _apply_strategy_filter(
    buy_signals: list[Signal],
    sell_signals: list[Signal],
    pivots: list[Pivot],
) -> tuple[list[Signal], list[Signal]]:
    """Phase 1: skip unwanted kinds + avoid trading inside pivot zones (except 类二)."""

    def _inside_pivot(sig: Signal) -> bool:
        """True if the signal price sits inside any bi-level pivot zone [ZD, ZG]."""
        if sig.kind == "second_class":
            return False  # 类二买卖点允许在中枢内
        for p in pivots:
            if p.level != "bi":
                continue
            if sig.idx < p.start_idx or sig.idx > p.end_idx:
                continue
            if p.zd <= sig.price <= p.zg:
                return True
        return False

    def _filter(signals: list[Signal]) -> list[Signal]:
        return [s for s in signals if s.kind not in _SKIP_KINDS and not _inside_pivot(s)]

    return _filter(buy_signals), _filter(sell_signals)


async def run_quick_backtest(repository: BinanceRepository, request: QuickBacktestRequest) -> QuickBacktestResponse:
    if request.start_time_ms is not None:
        candles = await repository.get_klines_history_from_time(
            request.symbol,
            request.interval,
            request.start_time_ms,
        )
        if request.end_time_ms is not None:
            candles = [c for c in candles if c.open_time <= request.end_time_ms]
    else:
        candles = await repository.get_klines_history(
            request.symbol, request.interval, settings.backtest_max_bars
        )

    hi_key = HIGHER_INTERVAL.get(request.interval)
    higher_strokes: list = []
    higher_pivots: list = []
    higher_interval: Optional[str] = None
    if hi_key:
        higher_need = max(120, min(settings.analyze_max_bars, len(candles) // 3))
        try:
            higher_raw = await repository.get_klines_history(request.symbol, hi_key, higher_need)
            higher_strokes, higher_pivots, _ = project_higher_onto_base(candles, higher_raw)
            higher_interval = hi_key
        except Exception:
            pass

    bundle = build_analyze_bundle(
        candles,
        market=request.market,
        symbol=request.symbol,
        interval=request.interval,
        higher_strokes=higher_strokes,
        higher_pivots=higher_pivots,
        warning_override=None,
        higher_interval=higher_interval,
    )

    composite = None
    tr = bundle.response.advanced_context.trend_recursion
    if tr:
        composite = tr.composite
    filtered_buy, filtered_sell = _apply_resonance_filter(
        bundle.all_buy_signals, bundle.all_sell_signals, composite,
    )

    # Phase 1: strategy filter (kind + pivot zone)
    filtered_buy, filtered_sell = _apply_strategy_filter(
        filtered_buy, filtered_sell, bundle.response.zhongshus,
    )

    trades, round_trips, final_eq, max_dd = _simulate(
        candles,
        strategy=request.strategy,
        fee_bps=request.fee_bps,
        initial_equity_usdt=request.initial_equity_usdt,
        leverage=request.leverage,
        buy_signals=filtered_buy,
        sell_signals=filtered_sell,
        trade_amount_usdt=request.trade_amount_usdt,
    )

    sl_hits = sum(1 for t in trades if t.exit_reason == "stop_loss")

    total_ret = (final_eq / request.initial_equity_usdt) - 1.0 if request.initial_equity_usdt > 0 else 0.0
    sharpe = _naive_sharpe(trades)
    stats_by_kind, win_rate, profit_factor, expectancy, max_cons, avg_win, avg_loss = _aggregate_round_trips(
        round_trips
    )

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
        stop_loss_hits=sl_hits,
    )

    return QuickBacktestResponse(
        metrics=metrics,
        trade_log=trades,
        closed_trades=round_trips,
        stats_by_signal_kind=stats_by_kind,
    )
