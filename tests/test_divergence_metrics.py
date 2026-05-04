from __future__ import annotations

from app.core.models import Candle, Direction, MacdPoint, Segment
from app.services.divergence_metrics import (
    DIVERGENCE_METRIC_ALGOS,
    divergence_pair_weakens,
    movement_metric_scalar,
)


def _c(i: int, vol: float = 1.0) -> Candle:
    t = 1_000_000 + i * 60_000
    return Candle(open_time=t, time=str(t), open=1.0, high=2.0, low=0.5, close=1.0, volume=vol)


def test_full_area_can_differ_from_abs_area() -> None:
    pts = [
        MacdPoint(dif=0.1, dea=0.05, hist=0.2),
        MacdPoint(dif=0.1, dea=0.06, hist=-0.12),
        MacdPoint(dif=0.0, dea=0.0, hist=0.15),
    ]
    a = Segment(
        start_bi=0,
        end_bi=0,
        start_idx=0,
        end_idx=2,
        start_price=1.0,
        end_price=1.0,
        direction=Direction.UP,
    )
    ar = movement_metric_scalar("area", pts, [], a)
    fa = movement_metric_scalar("full_area", pts, [], a)
    assert ar == abs(0.2) + abs(-0.12) + abs(0.15)
    assert fa == abs(0.2 + (-0.12) + 0.15)
    assert ar != fa


def test_metric_algo_registry_has_eleven_entries() -> None:
    assert len(DIVERGENCE_METRIC_ALGOS) == 11


def test_volume_sum_detects_weakening_pair() -> None:
    candles = [_c(i, 10.0 if i < 3 else 1.0) for i in range(8)]
    mpts = [MacdPoint(dif=0.0, dea=0.0, hist=1.0) for _ in candles]
    entry = Segment(
        start_bi=0,
        end_bi=0,
        start_idx=0,
        end_idx=2,
        start_price=1.0,
        end_price=1.1,
        direction=Direction.UP,
    )
    leaving = Segment(
        start_bi=0,
        end_bi=0,
        start_idx=3,
        end_idx=5,
        start_price=1.1,
        end_price=1.0,
        direction=Direction.DOWN,
    )
    assert divergence_pair_weakens("volume_sum", mpts, candles, entry, leaving, 0.9)

