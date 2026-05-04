"""风控与跟踪止盈止损（计算型工具，不含实盘下单）。"""

from __future__ import annotations

from app.core.models import (
    Candle,
    CompactOHLC,
    PositionSizingRequest,
    PositionSizingResponse,
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
    return PositionSizingResponse(risk_usdt=risk_usdt, suggested_quantity=qty, notional_usdt=notional)


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
