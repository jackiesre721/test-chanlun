from __future__ import annotations

from app.core.models import Candle, Direction, Stroke
from app.services.stroke_metrics import hydrate_stroke_metrics


def _bar(i: int, *, h: float = 2.0, l: float = 0.5, c: float = 1.0, v: float = 1.0) -> Candle:
    t = 1_000_000 + i * 60_000
    return Candle(open_time=t, time=str(t), open=1.0, high=h, low=l, close=c, volume=v)


def test_hydrate_stroke_metrics_sets_length_and_power() -> None:
    candles = [_bar(j) for j in range(10)]
    s = Stroke(
        start_idx=2,
        end_idx=5,
        start_price=1.0,
        end_price=2.0,
        direction=Direction.UP,
    )
    out = hydrate_stroke_metrics([s], candles)[0]
    assert out.length_bars == 4
    assert out.price_change == 1.0
    assert out.power_price == 1.0
    assert out.power_volume == 4.0
    assert out.slope_per_bar is not None
    assert out.rsq_close is not None
