"""演示级快速回测：全样本跑一次缠论流水线 + 极简成交模型（非业绩承诺）。"""

from __future__ import annotations

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
from app.services.analysis_pipeline import build_analyze_bundle


def _mark_equity_usdt(cash: float, btc_qty: float, px: float) -> float:
    return cash + btc_qty * px


def _simulate(
    candles: list[Candle],
    *,
    strategy: str,
    fee_bps: float,
    initial_equity_usdt: float,
    buy_signals: list[Signal],
    sell_signals: list[Signal],
) -> Tuple[list[QuickBacktestTrade], float, float]:
    fee_rate = fee_bps / 10_000
    cash = float(initial_equity_usdt)
    btc_qty = 0.0

    signals = sorted(
        buy_signals + sell_signals,
        key=lambda s: (s.idx, 0 if s.side == SignalSide.BUY else 1),
    )

    trades: list[QuickBacktestTrade] = []
    peak_equity = float(initial_equity_usdt)
    max_dd = 0.0

    def equity_at(px: float) -> float:
        return _mark_equity_usdt(cash, btc_qty, px)

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
            if cash <= 0:
                continue
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
            else:
                if btc_qty > 0:
                    qty = btc_qty
                    cash += qty * px * (1 - fee_rate)
                    btc_qty = 0.0
                    action = "SELL"
                elif btc_qty == 0:
                    if cash <= 0:
                        continue
                    qty_short = cash / (px * (1 + fee_rate))
                    btc_qty -= qty_short
                    cash += qty_short * px * (1 - fee_rate)
                    action = "SELL"
                else:
                    continue

        eq = equity_at(px)
        peak_equity = max(peak_equity, eq)
        if peak_equity > 0:
            max_dd = max(max_dd, (peak_equity - eq) / peak_equity)

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

    return trades, float(final_eq), float(max_dd)


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

    trades, final_eq, max_dd = _simulate(
        candles,
        strategy=request.strategy,
        fee_bps=request.fee_bps,
        initial_equity_usdt=request.initial_equity_usdt,
        buy_signals=bundle.all_buy_signals,
        sell_signals=bundle.all_sell_signals,
    )

    total_ret = (final_eq / request.initial_equity_usdt) - 1.0 if request.initial_equity_usdt > 0 else 0.0
    sharpe = _naive_sharpe(trades)

    metrics = QuickBacktestMetrics(
        bars_used=len(candles),
        trades=len(trades),
        final_equity_usdt=final_eq,
        total_return_fraction=float(total_ret),
        max_drawdown_fraction=float(max_dd),
        sharpe_naive=sharpe,
    )

    return QuickBacktestResponse(metrics=metrics, trade_log=trades)
