from __future__ import annotations

from app.core.models import Candle
from app.services.indicators import bollinger_bands, count_candle_gaps_in_range, rsi_wilder


def _c(i: int, **kwargs: float) -> Candle:
    t = 1_000_000 + i * 60_000
    o = kwargs.get("o", 1.0)
    h = kwargs.get("h", 2.0)
    l_ = kwargs.get("l", 0.5)
    c = kwargs.get("c", 1.0)
    v = kwargs.get("v", 1.0)
    return Candle(open_time=t, time=str(t), open=o, high=h, low=l_, close=c, volume=v)


def test_rsi_first_values_none_until_warm() -> None:
    closes = [1.0 + i * 0.01 for i in range(20)]
    r = rsi_wilder(closes, period=14)
    assert r[13] is None
    assert r[14] is not None


def test_bollinger_eventually_spreads_from_close() -> None:
    candles = [_c(i, c=100.0 + (i % 3)) for i in range(25)]
    b = bollinger_bands(candles, period=10, n_std=2.0)
    assert len(b) == len(candles)
    last = b[-1]
    assert last.upper >= last.mid >= last.lower


def test_count_gap_up_and_down() -> None:
    xs = [
        _c(0, h=10.0, l=8.0, c=9.0),
        _c(1, h=12.0, l=11.0, c=11.5),
        _c(2, h=7.0, l=5.0, c=6.0),
    ]
    up, dn = count_candle_gaps_in_range(xs, 0, 2)
    assert up == 1
    assert dn == 1
