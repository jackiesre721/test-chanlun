from typing import Optional

from app.core.models import Candle, MacdPoint, Signal, SignalSide, TdSummary


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append((value * alpha) + (out[-1] * (1 - alpha)))
    return out


def macd(candles: list[Candle], fast: int = 12, slow: int = 26, signal: int = 9) -> list[MacdPoint]:
    closes = [c.close for c in candles]
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    dif = [a - b for a, b in zip(fast_ema, slow_ema)]
    dea = ema(dif, signal)
    return [MacdPoint(dif=d, dea=e, hist=(d - e) * 2) for d, e in zip(dif, dea)]


def macd_area(points: list[MacdPoint], start_idx: int, end_idx: int) -> float:
    lo = max(0, min(start_idx, end_idx))
    hi = min(len(points) - 1, max(start_idx, end_idx))
    return sum(abs(points[i].hist) for i in range(lo, hi + 1))


def td_sequential(candles: list[Candle]) -> TdSummary:
    setup_up = 0
    setup_down = 0
    last_signal: Optional[Signal] = None

    for idx in range(4, len(candles)):
        close = candles[idx].close
        compare = candles[idx - 4].close
        if close > compare:
            setup_up += 1
            setup_down = 0
        elif close < compare:
            setup_down += 1
            setup_up = 0
        else:
            setup_up = 0
            setup_down = 0

        if setup_up == 9:
            last_signal = Signal(
                side=SignalSide.SELL,
                kind="td9",
                idx=idx,
                time=candles[idx].time,
                price=candles[idx].close,
                description="TD9 上涨计数完成，提示高位衰竭风险",
                strength=1.0,
            )
        elif setup_down == 9:
            last_signal = Signal(
                side=SignalSide.BUY,
                kind="td9",
                idx=idx,
                time=candles[idx].time,
                price=candles[idx].close,
                description="TD9 下跌计数完成，提示低位衰竭机会",
                strength=1.0,
            )

    return TdSummary(setup_up=setup_up, setup_down=setup_down, last_signal=last_signal)
