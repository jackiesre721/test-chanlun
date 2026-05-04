import math
from typing import Optional

from app.core.models import BollingerPoint, Candle, MacdPoint, Signal, SignalSide, TdSummary


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


def rsi_wilder(closes: list[float], period: int = 14) -> list[Optional[float]]:
    """Wilder RSI，与 K 线逐根对齐；前 `period` 根为 None（样本不足）。"""
    n = len(closes)
    out: list[Optional[float]] = [None] * n
    if n < period + 1 or period < 2:
        return out
    deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period

    def _rv(agv: float, alv: float) -> float:
        if alv < 1e-18:
            return 100.0
        rs = agv / alv
        return 100.0 - (100.0 / (1.0 + rs))

    out[period] = _rv(ag, al)
    for i in range(period, len(deltas)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        out[i + 1] = _rv(ag, al)
    return out


def bollinger_bands(
    candles: list[Candle],
    period: int = 20,
    n_std: float = 2.0,
) -> list[BollingerPoint]:
    """布林带（SMA ± n·σ），窗口不足时退化为当前收盘价三合一。"""
    closes = [c.close for c in candles]
    out: list[BollingerPoint] = []
    for i in range(len(closes)):
        if i + 1 < period:
            c = closes[i]
            out.append(BollingerPoint(mid=c, upper=c, lower=c))
            continue
        window = closes[i + 1 - period : i + 1]
        mid = sum(window) / period
        var = sum((x - mid) ** 2 for x in window) / period
        std = math.sqrt(max(var, 0.0))
        out.append(BollingerPoint(mid=mid, upper=mid + n_std * std, lower=mid - n_std * std))
    return out


def count_candle_gaps_in_range(candles: list[Candle], lo: int, hi: int) -> tuple[int, int]:
    """相邻 K 无重叠：向上缺口 / 向下缺口 计数（与 `chan_advanced` 原逻辑一致）。"""
    lo = max(0, lo)
    hi = min(len(candles) - 1, hi)
    up_gaps = 0
    dn_gaps = 0
    for i in range(lo + 1, hi + 1):
        prev, cur = candles[i - 1], candles[i]
        if cur.low > prev.high:
            up_gaps += 1
        if cur.high < prev.low:
            dn_gaps += 1
    return up_gaps, dn_gaps


def macd_area(points: list[MacdPoint], start_idx: int, end_idx: int) -> float:
    lo = max(0, min(start_idx, end_idx))
    hi = min(len(points) - 1, max(start_idx, end_idx))
    return sum(abs(points[i].hist) for i in range(lo, hi + 1))


def _true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr_last_wilder(highs: list[float], lows: list[float], closes: list[float], period: int) -> float:
    """Wilder ATR：返回序列最后一个 ATR 值。"""
    if len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("highs/lows/closes length mismatch")
    if period < 2:
        raise ValueError("period must be >= 2")
    if len(closes) < period + 1:
        raise ValueError("not enough bars for ATR")

    trs: list[float] = []
    for i in range(1, len(closes)):
        trs.append(_true_range(highs[i], lows[i], closes[i - 1]))

    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


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
