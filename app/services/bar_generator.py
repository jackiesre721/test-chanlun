"""由低周期 K 线按开盘时间分桶合成高周期 OHLCV（BarGenerator 语义，纯函数）。"""

from __future__ import annotations

from app.core.models import Candle


def interval_ms_from_minutes(minutes: int) -> int:
    if minutes < 1:
        raise ValueError("minutes must be >= 1")
    return int(minutes * 60_000)


def aggregate_candles_to_minutes(candles: list[Candle], target_minutes: int) -> list[Candle]:
    """同一桶内：open=首开盘，close=末收盘，high/low 极值，volume 求和；time 用首根 time。"""
    if not candles:
        return []
    step = interval_ms_from_minutes(target_minutes)
    buckets: dict[int, list[Candle]] = {}
    for c in sorted(candles, key=lambda x: x.open_time):
        key = (c.open_time // step) * step
        buckets.setdefault(key, []).append(c)
    out: list[Candle] = []
    for key in sorted(buckets.keys()):
        grp = buckets[key]
        first, last = grp[0], grp[-1]
        mx = max(x.high for x in grp)
        mn = min(x.low for x in grp)
        vol = sum(x.volume for x in grp)
        out.append(
            Candle(
                open_time=key,
                time=first.time,
                open=first.open,
                high=mx,
                low=mn,
                close=last.close,
                volume=vol,
            )
        )
    return out
