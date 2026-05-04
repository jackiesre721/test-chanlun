from __future__ import annotations

from app.core.models import Candle
from app.services.bar_generator import aggregate_candles_to_minutes


def _c(ms: int, close: float) -> Candle:
    return Candle(open_time=ms, time=str(ms), open=close - 0.1, high=close + 0.2, low=close - 0.3, close=close, volume=1.0)


def test_aggregate_five_minute_buckets() -> None:
    base = 1_700_000_000_000
    step = 60_000
    raw = [_c(base + i * step, float(100 + i)) for i in range(15)]
    out = aggregate_candles_to_minutes(raw, 5)
    assert len(out) == 4
