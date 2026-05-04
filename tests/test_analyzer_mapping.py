"""上级笔映射到本级：标准化 K 线 + open_time + higher_origin 元数据。"""

from __future__ import annotations

from app.core.models import Candle, Direction, Stroke
from app.services.analyzer import _map_stroke_to_base


def _bar(t: int) -> Candle:
    return Candle(
        open_time=t,
        time=str(t),
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.0,
        volume=1.0,
    )


def test_map_stroke_records_higher_origin_and_base_indices() -> None:
    higher_norm = [_bar(1_000_000 + i * 240_000) for i in range(6)]
    base_norm = [_bar(1_000_000 + i * 60_000) for i in range(24)]
    s = Stroke(start_idx=1, end_idx=3, start_price=1.0, end_price=2.0, direction=Direction.UP)
    out = _map_stroke_to_base(s, higher_norm, base_norm)
    assert out.higher_origin_bar_lo == 1
    assert out.higher_origin_bar_hi == 3
    assert out.higher_origin_open_time_lo == higher_norm[1].open_time
    assert out.higher_origin_open_time_hi == higher_norm[3].open_time
    assert 0 <= out.start_idx < len(base_norm)
    assert 0 <= out.end_idx < len(base_norm)
