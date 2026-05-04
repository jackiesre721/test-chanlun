"""chan_advanced：区间套、a+A+b+B+c、线段走势段、Zn、缺口。"""

from __future__ import annotations

from app.core.models import Candle, Direction, Pivot, Segment, Stroke
from app.services.chan_advanced import (
    build_abc_decomposition,
    build_chan_advanced_context,
    build_gap_stat_last_bi,
    build_nested_interval_analysis,
    build_segment_trend_runs,
)


def _c(i: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(
        open_time=i,
        time=f"t{i}",
        open=o,
        high=h,
        low=l,
        close=c,
        volume=1.0,
    )


def test_nested_interval_maps_higher_stroke_to_base_window() -> None:
    higher = [
        Stroke(start_idx=0, end_idx=10, start_price=1, end_price=2, direction=Direction.UP),
        Stroke(start_idx=10, end_idx=20, start_price=2, end_price=1, direction=Direction.DOWN),
    ]
    bis = [
        Stroke(start_idx=5, end_idx=7, start_price=1, end_price=1.1, direction=Direction.UP),
        Stroke(start_idx=7, end_idx=9, start_price=1.1, end_price=1.0, direction=Direction.DOWN),
    ]
    pivots: list[Pivot] = []
    candles = [_c(i, 1, 2, 0.5, 1) for i in range(30)]
    higher[0] = higher[0].model_copy(
        update={
            "higher_origin_bar_lo": 0,
            "higher_origin_bar_hi": 2,
            "higher_origin_open_time_lo": 1_000,
            "higher_origin_open_time_hi": 3_000,
        }
    )
    nested = build_nested_interval_analysis(
        base_interval="1",
        candles=candles,
        bis=bis,
        bi_pivots=pivots,
        higher_interval="15",
        higher_strokes=higher,
        max_slices=2,
    )
    assert nested is not None
    assert nested.higher_interval == "15"
    assert nested.alignment_rule_id == "higher_norm_half_open_to_base_norm_index_v1"
    assert len(nested.slices) == 2
    s0 = nested.slices[0]
    assert s0.candle_index_lo == 0 and s0.candle_index_hi == 10
    assert s0.sub_stroke_count >= 1
    assert s0.base_open_time_lo == 0 and s0.base_open_time_hi == 10
    assert s0.higher_open_time_lo == 1_000 and s0.higher_open_time_hi == 3_000


def test_abc_decomposition_two_stacked_pivots() -> None:
    strokes = [
        Stroke(start_idx=0, end_idx=1, start_price=10, end_price=8, direction=Direction.DOWN),
        Stroke(start_idx=1, end_idx=2, start_price=8, end_price=9, direction=Direction.UP),
        Stroke(start_idx=2, end_idx=3, start_price=9, end_price=7, direction=Direction.DOWN),
        Stroke(start_idx=3, end_idx=4, start_price=7, end_price=10, direction=Direction.UP),
    ]
    p0 = Pivot(start_bi=0, end_bi=1, start_idx=0, end_idx=2, zd=7.5, zg=9.5, level="bi")
    p1 = Pivot(start_bi=2, end_bi=3, start_idx=2, end_idx=4, zd=9.6, zg=11.0, level="bi")
    dec = build_abc_decomposition(strokes, [p0, p1])
    assert dec is not None
    labels = [p.label for p in dec.parts]
    assert "A" in labels and "B" in labels


def test_segment_trend_runs_merge_same_direction() -> None:
    segs = [
        Segment(start_bi=0, end_bi=1, start_idx=0, end_idx=1, start_price=10, end_price=8, direction=Direction.DOWN),
        Segment(start_bi=1, end_bi=2, start_idx=1, end_idx=2, start_price=8, end_price=7, direction=Direction.DOWN),
        Segment(start_bi=2, end_bi=3, start_idx=2, end_idx=3, start_price=7, end_price=9, direction=Direction.UP),
    ]
    from app.services.chan_engine import build_segment_pivots

    seg_pivots = build_segment_pivots(segs)
    runs = build_segment_trend_runs(segs, segment_engine="strict67", segment_pivots=seg_pivots)
    assert len(runs) == 2
    assert runs[0].direction == "DOWN" and runs[0].segment_count == 2
    assert runs[0].trend_type_code == "directional_extension"
    assert runs[0].trend_rule_table_id == "seg-zs-stack-overlap-v1"
    assert runs[0].segment_engine == "strict67"
    assert "contiguous_same_direction" in runs[0].merge_rule
    assert runs[1].direction == "UP"
    assert runs[1].trend_type_code == "neutral_single_segment"


def test_gap_stat_counts_adjacent_disjoint_bars() -> None:
    candles = [
        _c(0, 10, 10, 10, 10),
        _c(1, 12, 13, 12, 12),
        _c(2, 14, 15, 14, 14),
    ]
    s = Stroke(start_idx=0, end_idx=2, start_price=10, end_price=14, direction=Direction.UP)
    g = build_gap_stat_last_bi(candles, [s])
    assert g is not None
    assert g.up_gaps + g.down_gaps >= 0


def test_build_chan_advanced_context_always_returns_model() -> None:
    candles = [_c(i, 100, 101, 99, 100) for i in range(30)]
    bis = [
        Stroke(start_idx=0, end_idx=5, start_price=100, end_price=95, direction=Direction.DOWN),
        Stroke(start_idx=5, end_idx=10, start_price=95, end_price=98, direction=Direction.UP),
    ]
    pivots = [
        Pivot(start_bi=0, end_bi=1, start_idx=0, end_idx=10, zd=94, zg=99, level="bi"),
    ]
    segs: list[Segment] = []
    ctx = build_chan_advanced_context(
        base_interval="1",
        candles=candles,
        bis=bis,
        bi_pivots=pivots,
        segments=segs,
        segment_pivots=[],
        higher_interval=None,
        higher_strokes=[],
        segment_engine="legacy",
    )
    assert ctx.nested_interval is None
    assert ctx.segment_trend_runs == []
    assert ctx.trend_recursion is not None
    assert ctx.trend_recursion.composite == "insufficient_higher_data"
