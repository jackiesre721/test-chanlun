"""风控与跟踪止盈止损（计算型工具，不含实盘下单）。"""

from __future__ import annotations

from app.core.models import (
    Candle,
    CompactOHLC,
    PositionSizingRequest,
    PositionSizingResponse,
    Signal,
    SignalSide,
    TrailingStopRequest,
    TrailingStopResponse,
)
from app.services.indicators import atr_last_wilder

# Binance USDT-M futures minimum order quantities by symbol.
_MIN_QTY: dict[str, float] = {
    "BTCUSDT": 0.001,
    "ETHUSDT": 0.001,
    "SOLUSDT": 0.01,
    "XAUUSDT": 0.001,
    "DOGEUSDT": 1.0,
}
_DEFAULT_MIN_QTY = 0.001


def compute_position_size(req: PositionSizingRequest) -> PositionSizingResponse:
    risk_usdt = req.equity_usdt * req.risk_fraction
    move = abs(req.entry_price - req.stop_price)
    if move <= 0:
        raise ValueError("invalid entry/stop distance")
    qty = risk_usdt / move
    notional = qty * req.entry_price

    leverage = req.leverage
    required_margin = notional / leverage if leverage > 0 else notional
    effective_risk_pct = (risk_usdt / req.equity_usdt) * 100.0

    # Clamp to minimum order quantity
    min_qty = _MIN_QTY.get("DEFAULT", _DEFAULT_MIN_QTY)
    for sym, mq in _MIN_QTY.items():
        if sym in str(getattr(req, "symbol", "")):
            min_qty = mq
            break
    if qty < min_qty:
        qty = 0.0
        notional = 0.0
        required_margin = 0.0

    # Liquidation price considering available equity
    is_long = req.entry_price > req.stop_price
    margin = notional / leverage if leverage > 0 and qty > 0 else 0
    available_buffer = max(0.0, req.equity_usdt - margin)
    if qty > 0:
        if is_long:
            liq_price = req.entry_price * (1 + req.maint_margin_rate - 1 / leverage) - available_buffer / qty
        else:
            liq_price = req.entry_price * (1 - req.maint_margin_rate + 1 / leverage) + available_buffer / qty
    else:
        liq_price = None

    warnings: list[str] = []
    if req.risk_fraction > 0.01:
        warnings.append("单笔风险比例 >1%，偏离常见自省区间")
    if leverage > 5:
        warnings.append(f"杠杆 {leverage}x 超过 5x，清算风险显著增加")
    if qty == 0.0:
        warnings.append("计算仓位低于交易所最小下单量，已归零")

    return PositionSizingResponse(
        risk_usdt=risk_usdt,
        suggested_quantity=qty,
        notional_usdt=notional,
        leverage=leverage,
        required_margin=required_margin,
        liquidation_price=liq_price,
        effective_risk_pct=effective_risk_pct,
        warnings=warnings,
    )


def enrich_signals_with_sl_tp(
    signals: list[Signal],
    fractals: list,
    pivots: list,
    min_rr: float = 1.0,
    candles: list[Candle] | None = None,
    atr_period: int = 14,
    atr_multiplier: float = 1.5,
    max_tp_pct: float = 0.02,
) -> list[Signal]:
    """为每个信号推导止损（ATR-based / 中枢边界）和止盈（R:R 倍数）。"""
    if not signals:
        return signals

    # Compute ATR for ATR-based stop loss
    atr_val: float | None = None
    if candles and len(candles) > atr_period + 1:
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        atr_val = atr_last_wilder(highs, lows, closes, atr_period)

    enriched: list[Signal] = []
    for sig in signals:
        sl = _derive_stop_loss(sig, fractals, pivots, atr_val, atr_multiplier)
        tp = None
        rr = None
        if sl is not None:
            risk = abs(sig.price - sl)
            max_dist = sig.price * max_tp_pct
            tp_dist = min(risk * min_rr, max_dist)
            if risk > 0:
                if sig.side == SignalSide.BUY:
                    tp = sig.price + tp_dist
                else:
                    tp = sig.price - tp_dist
                rr = tp_dist / risk
        enriched.append(sig.model_copy(update={
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward_ratio": rr,
        }))
    return enriched


def _derive_stop_loss(
    sig: Signal,
    fractals: list,
    pivots: list,
    atr_val: float | None = None,
    atr_multiplier: float = 1.5,
) -> float | None:
    """ATR-based stop loss with pivot boundary fallback."""
    if sig.side == SignalSide.BUY:
        # Primary: ATR-based stop below nearest pivot ZD
        best_boundary = None
        for p in reversed(pivots):
            if p.zd < sig.price:
                best_boundary = float(p.zd)
                break
        if atr_val is not None and best_boundary is not None:
            return best_boundary - atr_multiplier * atr_val
        if atr_val is not None:
            return sig.price - atr_multiplier * atr_val
        # Fallback: fractal low
        for f in reversed(fractals):
            if f.type.value == "BOTTOM" and f.norm_idx < sig.idx and f.price < sig.price:
                return float(f.price)
        if best_boundary is not None:
            return best_boundary
        return None
    else:
        # Primary: ATR-based stop above nearest pivot ZG
        best_boundary = None
        for p in reversed(pivots):
            if p.zg > sig.price:
                best_boundary = float(p.zg)
                break
        if atr_val is not None and best_boundary is not None:
            return best_boundary + atr_multiplier * atr_val
        if atr_val is not None:
            return sig.price + atr_multiplier * atr_val
        # Fallback: fractal high
        for f in reversed(fractals):
            if f.type.value == "TOP" and f.norm_idx < sig.idx and f.price > sig.price:
                return float(f.price)
        if best_boundary is not None:
            return best_boundary
        return None


def compute_trailing_stop(req: TrailingStopRequest) -> TrailingStopResponse:
    highs = [bar.high for bar in req.ohlc_tail]
    lows = [bar.low for bar in req.ohlc_tail]
    closes = [bar.close for bar in req.ohlc_tail]
    atr_val = atr_last_wilder(highs, lows, closes, req.atr_period)

    if req.direction == "LONG":
        peak = req.peak_price if req.peak_price is not None else max(highs)
        stop = peak - atr_val * req.atr_multiplier
    else:
        trough = req.trough_price if req.trough_price is not None else min(lows)
        stop = trough + atr_val * req.atr_multiplier

    return TrailingStopResponse(atr=atr_val, stop_price=stop, mode="atr_trailing")


def compact_ohlc_from_candles_tail(candles: list[Candle], max_len: int = 240) -> list[CompactOHLC]:
    """从 Candle 列表尾部截取 OHLC（用于把 /analyze 结果喂给 trailing 接口）。"""
    tail = candles[-max_len:]
    return [CompactOHLC(high=c.high, low=c.low, close=c.close) for c in tail]
