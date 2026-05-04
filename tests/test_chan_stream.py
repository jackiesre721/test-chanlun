from __future__ import annotations

from app.core.models import Candle, Market
from app.services.chan_stream import ChanVirtualPenSession


def _c(t: int) -> Candle:
    return Candle(open_time=t, time=str(t), open=1.0, high=2.0, low=0.5, close=1.0, volume=1.0)


def test_virtual_pen_pop_and_rebuild_smaller_window() -> None:
    bars = [_c(1_000_000 + i * 60_000) for i in range(120)]
    sess = ChanVirtualPenSession(
        market=Market.CRYPTO,
        symbol="BTCUSDT",
        interval="60",
        higher_strokes=[],
        higher_pivots=[],
    )
    sess.replace_all(bars)
    b1 = sess.rebuild_bundle()
    sess.pop_last()
    b2 = sess.rebuild_bundle()
    assert len(sess.candles) == 119
    assert len(b2.response.kline_data) <= len(b1.response.kline_data)
    assert b2.response.rules_version == b1.response.rules_version
