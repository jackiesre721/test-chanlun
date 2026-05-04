from __future__ import annotations

from app.core.models import Candle, Direction, Pivot
from app.services.pivot_symmetry import is_symmetry_zs, pivot_symmetry_balance


def _k(i: int, close: float) -> Candle:
    t = i * 60_000
    return Candle(open_time=t, time=str(t), open=close, high=close + 0.5, low=close - 0.5, close=close, volume=1.0)


def test_balance_perfect_when_split_even() -> None:
    candles = [_k(i, 102.0 if i < 5 else 98.0) for i in range(10)]
    p = Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=9, zg=101.0, zd=99.0, level="bi", direction=Direction.UP)
    b = pivot_symmetry_balance(candles, p)
    assert b == 1.0
    assert is_symmetry_zs(candles, p, min_balance=0.9)
