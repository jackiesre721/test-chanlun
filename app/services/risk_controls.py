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

    # USDT 永续合约强平价（简化 tier-1）
    is_long = req.entry_price > req.stop_price
    if is_long:
        liq_price = req.entry_price * (1 - 1 / leverage + req.maint_margin_rate)
    else:
        liq_price = req.entry_price * (1 + 1 / leverage - req.maint_margin_rate)

    warnings: list[str] = []
    if req.risk_fraction > 0.01:
        warnings.append("单笔风险比例 >1%，偏离常见自省区间")
    if leverage > 5:
        warnings.append(f"杠杆 {leverage}x 超过 5x，清算风险显著增加")

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
    min_rr: float = 2.0,
) -> list[Signal]:
    """为每个信号推导止损（分型极值 / 中枢边界）和止盈（R:R 倍数）。"""
    if not signals:
        return signals

    enriched: list[Signal] = []
    for sig in signals:
        sl = _derive_stop_loss(sig, fractals, pivots)
        tp = None
        rr = None
        if sl is not None:
            risk = abs(sig.price - sl)
            if risk > 0:
                if sig.side == SignalSide.BUY:
                    tp = sig.price + risk * min_rr
                else:
                    tp = sig.price - risk * min_rr
                rr = abs(sig.price - tp) / risk
        enriched.append(sig.model_copy(update={
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward_ratio": rr,
        }))
    return enriched


def _derive_stop_loss(sig: Signal, fractals: list, pivots: list) -> float | None:
    """从分型极值推导止损价，fallback 到中枢边界。"""
    if sig.side == SignalSide.BUY:
        # 向后搜索最近的底分型极值
        for f in reversed(fractals):
            if f.type.value == "BOTTOM" and f.norm_idx < sig.idx and f.price < sig.price:
                return float(f.price)
        # Fallback: 中枢 ZD
        for p in reversed(pivots):
            if p.zd < sig.price:
                return float(p.zd)
        return None
    else:
        # SELL: 向后搜索最近的顶分型极值
        for f in reversed(fractals):
            if f.type.value == "TOP" and f.norm_idx < sig.idx and f.price > sig.price:
                return float(f.price)
        # Fallback: 中枢 ZG
        for p in reversed(pivots):
            if p.zg > sig.price:
                return float(p.zg)
        return None


def compute_trailing_stop(req: TrailingStopRequest) -> TrailingStopResponse:
    highs = [bar.high for bar in req.ohlc_tail]
    lows = [bar.low for bar in req.ohlc_tail]
    closes = [bar.close for bar in req.ohlc_tail]
    atr_val = atr_last_wilder(highs, lows, closes, req.atr_period)

    if req.direction == "LONG":
        peak = req.peak_price if req.peak_price is not None else max(closes)
        stop = peak - atr_val * req.atr_multiplier
    else:
        trough = req.trough_price if req.trough_price is not None else min(lows)
        stop = trough + atr_val * req.atr_multiplier

    return TrailingStopResponse(atr=atr_val, stop_price=stop, mode="atr_trailing")


def compact_ohlc_from_candles_tail(candles: list[Candle], max_len: int = 240) -> list[CompactOHLC]:
    """从 Candle 列表尾部截取 OHLC（用于把 /analyze 结果喂给 trailing 接口）。"""
    tail = candles[-max_len:]
    return [CompactOHLC(high=c.high, low=c.low, close=c.close) for c in tail]
