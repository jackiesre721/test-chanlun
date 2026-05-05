"""演示级快速回测：全样本跑一次缠论流水线 + 信号驱动成交模型（非业绩承诺）。"""

from __future__ import annotations

import asyncio
import math
from statistics import mean, pstdev
from typing import Optional, Tuple

from app.core.config import settings
from app.core.models import (
    Candle,
    QuickBacktestMetrics,
    QuickBacktestRequest,
    QuickBacktestResponse,
    QuickBacktestTrade,
    Signal,
    SignalSide,
)
from app.repositories.market_data import BinanceRepository
from app.services.analyzer import HIGHER_INTERVAL, project_higher_onto_base
from app.services.analysis_pipeline import build_analyze_bundle


def _simulate(
    candles: list[Candle],
    *,
    strategy: str,
    fee_bps: float,
    initial_equity_usdt: float,
    leverage: int,
    buy_signals: list[Signal],
    sell_signals: list[Signal],
    trade_amount_usdt: float | None = None,
) -> Tuple[list[QuickBacktestTrade], float, float]:
    """Backtest simulation with optional fixed per-trade margin.

    When trade_amount_usdt is set, each trade uses exactly that amount as margin
    (no compounding).  When None, uses all available equity (legacy compounding).
    Includes signal-based stop-loss exit and leverage-based liquidation.
    """
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
    peak_equity = float(initial_equity_usdt)
    max_dd = 0.0

    # --- Position state ---
    pos_qty: float = 0.0        # coins (>0 long, <0 short)
    pos_entry: float = 0.0      # entry price
    pos_margin: float = 0.0     # margin locked
    active_sl: float | None = None  # signal stop-loss price
    balance: float = float(initial_equity_usdt)  # total account value

    # ---- helpers ----
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

    def _close(bar_idx: int, time_str: str, close_px: float, reason: str) -> None:
        nonlocal balance, pos_qty, pos_entry, pos_margin, active_sl
        if pos_qty > 0:
            pnl = pos_qty * close_px * (1 - fee_rate) - pos_qty * pos_entry
        else:
            pnl = (abs(pos_qty) * pos_entry * (1 - fee_rate)
                   - abs(pos_qty) * close_px * (1 + fee_rate))
        # Cap loss at margin (liquidation shouldn't exceed margin)
        pnl = max(-pos_margin, pnl)
        balance += pnl
        if balance < 0:
            balance = 0.0
        action = "SELL" if pos_qty > 0 else "BUY"
        eq = balance  # position is flat
        _update_peak_dd(eq)
        trades.append(QuickBacktestTrade(
            bar_idx=bar_idx, time=time_str, action=action,
            price=float(close_px), equity_after=float(eq),
            exit_reason=reason, quantity=abs(pos_qty),
        ))
        pos_qty = 0.0
        pos_entry = 0.0
        pos_margin = 0.0
        active_sl = None

    def _open(sig: Signal, px: float, candle: Candle, side: str) -> bool:
        nonlocal pos_qty, pos_entry, pos_margin, active_sl
        margin = min(fixed_margin, balance) if fixed_margin else balance
        if margin <= 0:
            return False
        qty = margin * lev / (px * (1 + fee_rate))
        pos_qty = qty if side == "BUY" else -qty
        pos_entry = px
        pos_margin = margin
        active_sl = sig.stop_loss
        eq = _equity(px)
        _update_peak_dd(eq)
        trades.append(QuickBacktestTrade(
            bar_idx=sig.idx, time=candle.time, action=side,
            price=float(px), equity_after=float(eq),
            exit_reason="signal", quantity=abs(pos_qty),
            stop_loss=sig.stop_loss, take_profit_1=sig.take_profit_1,
            take_profit_2=sig.take_profit,
        ))
        return True

    # ---- main loop ----
    for bar_idx, candle in enumerate(candles):
        # 1) Stop-loss check
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

        # 2) Liquidation check (lev > 1)
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

        # 3) Process signals
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
    return trades, float(final_eq), float(max_dd)


def _compute_trade_metrics(trades: list[QuickBacktestTrade]) -> Tuple[Optional[float], Optional[float]]:
    if len(trades) < 2:
        return None, None
    equity_changes: list[float] = []
    for prev, nxt in zip(trades, trades[1:]):
        if prev.equity_after > 0:
            equity_changes.append(nxt.equity_after - prev.equity_after)
    if not equity_changes:
        return None, None
    wins = [c for c in equity_changes if c > 0]
    losses = [c for c in equity_changes if c < 0]
    total = len(equity_changes)
    win_rate = len(wins) / total if total > 0 else None
    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None
    return win_rate, profit_factor


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
        # Divergent: only allow first-class signals (strongest structural turns)
        return [s for s in buy_signals if s.kind == "first"], [s for s in sell_signals if s.kind == "first"]
    return buy_signals, sell_signals


async def run_quick_backtest(repository: BinanceRepository, request: QuickBacktestRequest) -> QuickBacktestResponse:
    # Fetch base candles
    if request.start_time_ms is not None:
        candles = await repository.get_klines_history_from_time(
            request.symbol, request.interval, request.start_time_ms,
        )
        # Trim to end_time_ms if specified
        if request.end_time_ms is not None:
            candles = [c for c in candles if c.open_time <= request.end_time_ms]
    else:
        candles = await repository.get_klines_history(request.symbol, request.interval, settings.backtest_max_bars)

    # Fetch higher-timeframe candles for multi-TF resonance
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
            pass  # proceed without higher-level data

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

    # Apply multi-timeframe resonance filter
    composite = None
    tr = bundle.response.advanced_context.trend_recursion
    if tr:
        composite = tr.composite
    filtered_buy, filtered_sell = _apply_resonance_filter(
        bundle.all_buy_signals, bundle.all_sell_signals, composite,
    )

    trades, final_eq, max_dd = _simulate(
        candles,
        strategy=request.strategy,
        fee_bps=request.fee_bps,
        initial_equity_usdt=request.initial_equity_usdt,
        leverage=request.leverage,
        buy_signals=filtered_buy,
        sell_signals=filtered_sell,
        trade_amount_usdt=request.trade_amount_usdt,
    )

    total_ret = (final_eq / request.initial_equity_usdt) - 1.0 if request.initial_equity_usdt > 0 else 0.0
    sharpe = _naive_sharpe(trades)
    win_rate, profit_factor = _compute_trade_metrics(trades)

    metrics = QuickBacktestMetrics(
        bars_used=len(candles),
        trades=len(trades),
        final_equity_usdt=final_eq,
        total_return_fraction=float(total_ret),
        max_drawdown_fraction=float(max_dd),
        sharpe_naive=sharpe,
        win_rate=win_rate,
        profit_factor=profit_factor,
        stop_loss_hits=0,
    )

    return QuickBacktestResponse(metrics=metrics, trade_log=trades)
