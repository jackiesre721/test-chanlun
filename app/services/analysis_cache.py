"""分析侧轻量缓存（MACD 等纯函数重复计算）。"""

from __future__ import annotations

from collections import OrderedDict

from app.core.config import settings
from app.core.models import Candle, MacdPoint
from app.services import indicators

_macd_cache: OrderedDict[tuple, list[MacdPoint]] = OrderedDict()


def _macd_cache_key(candles: list[Candle]) -> tuple:
    if not candles:
        return (0,)
    tail = tuple((c.open_time, round(c.close, 8)) for c in candles[-4:])
    return (len(candles), candles[0].open_time, candles[-1].open_time, tail)


def display_macd_for_analysis(candles: list[Candle]) -> list[MacdPoint]:
    """与 `indicators.macd` 等价；在窗口指纹命中时复用结果。"""
    if settings.macd_cache_max_entries <= 0:
        return indicators.macd(candles)
    key = _macd_cache_key(candles)
    if key in _macd_cache:
        _macd_cache.move_to_end(key)
        return _macd_cache[key]
    pts = indicators.macd(candles)
    _macd_cache[key] = pts
    while len(_macd_cache) > settings.macd_cache_max_entries:
        _macd_cache.popitem(last=False)
    return pts
