from app.core.models import Candle, Direction, SignalSide
from app.services.chan_engine import (
    build_active_stroke,
    build_divergences,
    build_pivots,
    build_segment_pivots,
    build_segments,
    build_signals,
    build_strokes,
    build_t1p_pan_signals,
    find_fractals,
    normalize_candles,
)


def _candle(idx: int, high: float, low: float) -> Candle:
    return Candle(
        open_time=idx,
        time=f"t{idx}",
        open=(high + low) / 2,
        high=high,
        low=low,
        close=(high + low) / 2,
        volume=1,
        source_idx=idx,
        high_idx=idx,
        low_idx=idx,
    )


def _flat_macd(length: int, value: float = 1.0):
    from app.core.models import MacdPoint

    return [MacdPoint(dif=value, dea=0, hist=value) for _ in range(length)]


def test_fractals_and_strokes_are_built_from_alternating_extremes() -> None:
    candles = [
        _candle(0, 10, 8),
        _candle(1, 12, 9),
        _candle(2, 11, 8),
        _candle(3, 10, 7),
        _candle(4, 9, 5),
        _candle(5, 10, 6),
        _candle(6, 12, 7),
        _candle(7, 15, 10),
        _candle(8, 13, 9),
        _candle(9, 12, 8),
        _candle(10, 11, 6),
        _candle(11, 12, 7),
        _candle(12, 14, 8),
        _candle(13, 16, 11),
        _candle(14, 15, 10),
    ]

    normalized = normalize_candles(candles)
    fractals = find_fractals(normalized)
    strokes = build_strokes(fractals, min_gap=2, candles=normalized)

    assert len(fractals) >= 4
    assert len(strokes) >= 2
    assert strokes[0].start_idx < strokes[0].end_idx


def test_top_fractal_requires_middle_low_strict_highest_among_three() -> None:
    """62 课标准顶分型：中间 K 低点须高于左右低点，否则不成立。"""
    candles = [
        _candle(0, 10.0, 9.0),
        _candle(1, 12.0, 8.0),
        _candle(2, 11.0, 9.5),
    ]
    assert find_fractals(candles) == []


def test_segment_pivot_three_segments_only_when_no_fourth() -> None:
    """仅三段线段重叠、尚无离开段时也应给出中枢（leave 可为 None）。"""
    from app.core.models import Direction, Segment

    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=10, end_price=20, direction=Direction.UP),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=18, end_price=12, direction=Direction.DOWN),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=14, end_price=22, direction=Direction.UP),
    ]
    pivots = build_segment_pivots(segments)
    assert len(pivots) == 1
    assert pivots[0].leave_seg_idx is None
    assert pivots[0].start_bi == 0


def test_inclusion_keeps_real_high_low_source_indices() -> None:
    candles = [
        _candle(0, 10, 8),
        _candle(1, 12, 9),
        _candle(2, 11, 10),  # contained by previous candle
        _candle(3, 13, 11),
    ]

    normalized = normalize_candles(candles)

    assert normalized[1].high == 12
    assert normalized[1].high_idx == 1
    assert normalized[1].low == 10
    assert normalized[1].low_idx == 2
    assert normalized[1].merged_from == [1, 2]


def test_too_close_opposite_fractal_replaces_previous_extreme_without_reversing_time() -> None:
    from app.core.models import PointType, Fractal

    fractals = [
        Fractal(idx=1, norm_idx=1, type=PointType.TOP, price=10, time="t1"),
        Fractal(idx=4, norm_idx=4, type=PointType.BOTTOM, price=8, time="t4"),
        Fractal(idx=5, norm_idx=5, type=PointType.TOP, price=12, time="t5"),
        Fractal(idx=11, norm_idx=11, type=PointType.BOTTOM, price=6, time="t11"),
    ]

    strokes = build_strokes(fractals, min_gap=5)

    assert len(strokes) == 1
    assert strokes[0].start_idx == 5
    assert strokes[0].end_idx == 11


def test_strict_stroke_requires_endpoint_extremes_inside_span() -> None:
    from app.core.models import PointType, Fractal

    candles = [
        _candle(0, 10, 8),
        _candle(1, 9, 6),
        _candle(2, 13, 7),
        _candle(3, 12, 8),
        _candle(4, 14, 9),
        _candle(5, 13, 10),
    ]
    fractals = [
        Fractal(idx=1, norm_idx=1, type=PointType.BOTTOM, price=6, time="t1"),
        Fractal(idx=3, norm_idx=3, type=PointType.TOP, price=12, time="t3"),
    ]

    assert build_strokes(fractals, min_gap=2, candles=candles) == []


def test_last_stroke_extends_when_same_direction_makes_new_extreme() -> None:
    from app.core.models import PointType, Fractal

    fractals = [
        Fractal(idx=0, norm_idx=0, type=PointType.BOTTOM, price=10, time="t0"),
        Fractal(idx=5, norm_idx=5, type=PointType.TOP, price=20, time="t5"),
        Fractal(idx=7, norm_idx=7, type=PointType.BOTTOM, price=15, time="t7"),
        Fractal(idx=9, norm_idx=9, type=PointType.TOP, price=22, time="t9"),
    ]

    strokes = build_strokes(fractals, min_gap=4)

    assert len(strokes) == 1
    assert strokes[0].start_idx == 0
    assert strokes[0].end_idx == 9
    assert strokes[0].end_price == 22


def test_last_stroke_is_broken_when_invalid_reverse_breaks_start_extreme() -> None:
    from app.core.models import PointType, Fractal

    fractals = [
        Fractal(idx=0, norm_idx=0, type=PointType.BOTTOM, price=10, time="t0"),
        Fractal(idx=5, norm_idx=5, type=PointType.TOP, price=20, time="t5"),
        Fractal(idx=7, norm_idx=7, type=PointType.BOTTOM, price=9, time="t7"),
        Fractal(idx=12, norm_idx=12, type=PointType.TOP, price=21, time="t12"),
    ]

    strokes = build_strokes(fractals, min_gap=4)

    assert len(strokes) == 1
    assert strokes[0].start_idx == 7
    assert strokes[0].end_idx == 12
    assert strokes[0].start_price == 9


def test_pivot_is_created_when_three_strokes_overlap() -> None:
    from app.core.models import Direction, Stroke

    # Direct stroke setup keeps this test focused on pivot overlap rules.
    pivots = build_pivots(
        [
            Stroke(start_idx=0, end_idx=5, start_price=10, end_price=20, direction=Direction.UP),
            Stroke(start_idx=5, end_idx=10, start_price=20, end_price=12, direction=Direction.DOWN),
            Stroke(start_idx=10, end_idx=15, start_price=12, end_price=18, direction=Direction.UP),
        ]
    )

    assert len(pivots) == 1
    assert pivots[0].zd < pivots[0].zg
    assert pivots[0].level == "bi"


def test_duplicate_same_direction_pivots_are_merged() -> None:
    from app.core.models import Direction, Stroke

    strokes = [
        Stroke(start_idx=0, end_idx=5, start_price=10, end_price=20, direction=Direction.UP),
        Stroke(start_idx=5, end_idx=10, start_price=20, end_price=10, direction=Direction.DOWN),
        Stroke(start_idx=10, end_idx=15, start_price=10, end_price=20, direction=Direction.UP),
        Stroke(start_idx=15, end_idx=20, start_price=10, end_price=20, direction=Direction.UP),
        Stroke(start_idx=20, end_idx=25, start_price=10, end_price=20, direction=Direction.UP),
    ]

    pivots = build_pivots(strokes)

    assert len(pivots) == 1
    assert pivots[0].start_idx == 0
    assert pivots[0].end_idx == 25


def test_segments_are_built_from_three_or_more_strokes() -> None:
    from app.core.models import Direction, Stroke

    strokes = [
        Stroke(start_idx=0, end_idx=5, start_price=10, end_price=20, direction=Direction.UP),
        Stroke(start_idx=5, end_idx=10, start_price=20, end_price=12, direction=Direction.DOWN),
        Stroke(start_idx=10, end_idx=15, start_price=12, end_price=22, direction=Direction.UP),
        Stroke(start_idx=15, end_idx=20, start_price=22, end_price=14, direction=Direction.DOWN),
        Stroke(start_idx=20, end_idx=25, start_price=14, end_price=24, direction=Direction.UP),
    ]

    segments = build_segments(strokes)

    assert segments
    assert segments[0].start_bi == 0
    assert segments[0].end_bi >= 2
    assert segments[0].direction == Direction.UP


def test_segments_require_first_three_strokes_to_overlap() -> None:
    from app.core.models import Direction, Stroke

    strokes = [
        Stroke(start_idx=0, end_idx=5, start_price=10, end_price=20, direction=Direction.UP),
        Stroke(start_idx=5, end_idx=10, start_price=20, end_price=15, direction=Direction.DOWN),
        Stroke(start_idx=10, end_idx=15, start_price=21, end_price=25, direction=Direction.UP),
    ]

    assert build_segments(strokes) == []


def test_segments_alternate_directions() -> None:
    from app.core.models import Direction, Stroke

    strokes = [
        Stroke(start_idx=0, end_idx=5, start_price=10, end_price=20, direction=Direction.UP),
        Stroke(start_idx=5, end_idx=10, start_price=20, end_price=12, direction=Direction.DOWN),
        Stroke(start_idx=10, end_idx=15, start_price=12, end_price=22, direction=Direction.UP),
        Stroke(start_idx=15, end_idx=20, start_price=22, end_price=14, direction=Direction.DOWN),
        Stroke(start_idx=20, end_idx=25, start_price=14, end_price=24, direction=Direction.UP),
        Stroke(start_idx=25, end_idx=30, start_price=24, end_price=16, direction=Direction.DOWN),
        Stroke(start_idx=30, end_idx=35, start_price=16, end_price=26, direction=Direction.UP),
    ]

    segments = build_segments(strokes)

    assert all(left.direction != right.direction for left, right in zip(segments, segments[1:]))


def test_segment_pivot_extends_while_new_segment_overlaps() -> None:
    from app.core.models import Direction, Segment

    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=8, end_price=18, direction=Direction.UP),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=18, end_price=12, direction=Direction.DOWN),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=14, end_price=22, direction=Direction.UP),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=17, end_price=13, direction=Direction.DOWN),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=16, end_price=19, direction=Direction.UP),
        Segment(start_bi=10, end_bi=12, start_idx=25, end_idx=30, start_price=18, end_price=24, direction=Direction.UP),
    ]

    pivots = build_segment_pivots(segments)

    assert len(pivots) == 1
    assert pivots[0].start_bi == 0
    assert pivots[0].end_bi == 4
    assert pivots[0].zd == 16
    assert pivots[0].zg == 17


def test_segment_pivot_extension_keeps_initial_price_range() -> None:
    from app.core.models import Direction, Segment

    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=8, end_price=18, direction=Direction.UP),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=18, end_price=12, direction=Direction.DOWN),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=14, end_price=22, direction=Direction.UP),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=17, end_price=13, direction=Direction.DOWN),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=16, end_price=19, direction=Direction.UP),
        Segment(start_bi=10, end_bi=12, start_idx=25, end_idx=30, start_price=18, end_price=24, direction=Direction.UP),
    ]

    pivot = build_segment_pivots(segments)[0]

    assert pivot.zd == 16
    assert pivot.zg == 17
    assert pivot.start_bi == 0
    assert pivot.end_bi == 4


def test_divergence_structure_kind_trend_vs_zpan() -> None:
    from app.core.models import Pivot

    from app.services.chan_engine import _divergence_structure_kind

    p_stack = [
        Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=1, zd=10.0, zg=20.0, level="segment"),
        Pivot(start_bi=3, end_bi=5, start_idx=2, end_idx=3, zd=25.0, zg=35.0, level="segment"),
    ]
    assert _divergence_structure_kind(p_stack, 1) == "trend"

    p_overlap = [
        Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=1, zd=15.0, zg=28.0, level="segment"),
        Pivot(start_bi=3, end_bi=5, start_idx=2, end_idx=3, zd=18.0, zg=30.0, level="segment"),
    ]
    assert _divergence_structure_kind(p_overlap, 1) == "zpan_like"
    assert _divergence_structure_kind(p_stack, 0) == "zpan_like"


def test_bi_pivot_can_generate_divergence_without_segments() -> None:
    from app.core.models import Direction, Stroke

    strokes = [
        Stroke(start_idx=0, end_idx=5, start_price=20, end_price=50, direction=Direction.UP),
        Stroke(start_idx=5, end_idx=10, start_price=50, end_price=35, direction=Direction.DOWN),
        Stroke(start_idx=10, end_idx=15, start_price=35, end_price=48, direction=Direction.UP),
        Stroke(start_idx=15, end_idx=20, start_price=48, end_price=37, direction=Direction.DOWN),
        Stroke(start_idx=20, end_idx=25, start_price=37, end_price=48, direction=Direction.UP),
        Stroke(start_idx=25, end_idx=30, start_price=48, end_price=70, direction=Direction.UP),
    ]
    macd = _flat_macd(35, 1.0)
    for idx in range(0, 6):
        macd[idx].hist = 10

    pivots = build_pivots(strokes)
    divergences = build_divergences(strokes, pivots, macd)

    assert pivots[0].level == "bi"
    assert len(divergences) == 1
    assert divergences[0].level == "bi"


def test_first_buy_signal_requires_leaving_pivot_divergence() -> None:
    from app.core.models import Direction, Pivot, Segment

    candles = [_candle(idx, 100 - idx, 90 - idx) for idx in range(40)]
    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=100, end_price=80, direction=Direction.DOWN),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=80, end_price=95, direction=Direction.UP),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=95, end_price=85, direction=Direction.DOWN),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=85, end_price=93, direction=Direction.UP),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=93, end_price=75, direction=Direction.DOWN),
    ]
    pivot = Pivot(start_bi=1, end_bi=3, start_idx=5, end_idx=20, zd=85, zg=93)
    macd = _flat_macd(40, 1.0)
    for idx in range(0, 6):
        macd[idx].hist = 10
    for idx in range(20, 26):
        macd[idx].hist = 1

    divergences = build_divergences(segments, [pivot], macd)
    buy_signals, sell_signals = build_signals(candles, segments, [pivot], divergences)

    assert not sell_signals
    assert len(divergences) == 1
    assert divergences[0].structure_kind == "zpan_like"
    assert "盘整类背驰" in divergences[0].description
    assert divergences[0].entry_seg_idx == 0
    assert divergences[0].leave_seg_idx == 4
    assert len(buy_signals) == 1
    assert buy_signals[0].kind == "first"
    assert buy_signals[0].side == "BUY"
    assert buy_signals[0].evidence is not None


def test_no_signal_without_segment_divergence() -> None:
    from app.core.models import Direction, Pivot, Segment

    candles = [_candle(idx, 100 - idx, 90 - idx) for idx in range(40)]
    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=100, end_price=80, direction=Direction.DOWN),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=80, end_price=95, direction=Direction.UP),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=95, end_price=85, direction=Direction.DOWN),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=85, end_price=93, direction=Direction.UP),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=93, end_price=75, direction=Direction.DOWN),
    ]
    pivot = Pivot(start_bi=1, end_bi=3, start_idx=5, end_idx=20, zd=85, zg=93)
    macd = _flat_macd(40, 5.0)

    divergences = build_divergences(segments, [pivot], macd)
    buy_signals, sell_signals = build_signals(candles, segments, [pivot], divergences)

    assert divergences == []
    assert buy_signals == []
    assert sell_signals == []


def test_divergence_ratio_threshold_is_configurable() -> None:
    from app.core.models import Direction, Pivot, Segment

    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=100, end_price=80, direction=Direction.DOWN),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=80, end_price=95, direction=Direction.UP),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=95, end_price=85, direction=Direction.DOWN),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=85, end_price=93, direction=Direction.UP),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=93, end_price=75, direction=Direction.DOWN),
    ]
    pivot = Pivot(start_bi=1, end_bi=3, start_idx=5, end_idx=20, zd=85, zg=93)
    macd = _flat_macd(40, 1.0)
    for idx in range(0, 6):
        macd[idx].hist = 10
    for idx in range(20, 26):
        macd[idx].hist = 7

    assert build_divergences(segments, [pivot], macd, max_area_ratio=0.8)
    assert build_divergences(segments, [pivot], macd, max_area_ratio=0.6) == []


def test_divergence_requires_minimum_breakout() -> None:
    from app.core.models import Direction, Pivot, Segment

    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=100, end_price=80, direction=Direction.DOWN),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=80, end_price=95, direction=Direction.UP),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=95, end_price=85, direction=Direction.DOWN),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=85, end_price=93, direction=Direction.UP),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=93, end_price=79.7, direction=Direction.DOWN),
    ]
    pivot = Pivot(start_bi=1, end_bi=3, start_idx=5, end_idx=20, zd=85, zg=93)
    macd = _flat_macd(40, 1.0)
    for idx in range(0, 6):
        macd[idx].hist = 10

    assert build_divergences(segments, [pivot], macd, min_breakout_ratio=0.0)
    assert build_divergences(segments, [pivot], macd, min_breakout_ratio=0.1) == []


def test_second_buy_signal_requires_retest_above_first_buy_low() -> None:
    from app.core.models import Direction, Pivot, Segment

    candles = [_candle(idx, 100 - idx, 90 - idx) for idx in range(50)]
    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=100, end_price=80, direction=Direction.DOWN),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=80, end_price=95, direction=Direction.UP),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=95, end_price=85, direction=Direction.DOWN),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=85, end_price=93, direction=Direction.UP),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=93, end_price=75, direction=Direction.DOWN),
        Segment(start_bi=10, end_bi=12, start_idx=25, end_idx=30, start_price=75, end_price=88, direction=Direction.UP),
        Segment(start_bi=12, end_bi=14, start_idx=30, end_idx=35, start_price=88, end_price=78, direction=Direction.DOWN),
    ]
    pivot = Pivot(start_bi=1, end_bi=3, start_idx=5, end_idx=20, zd=85, zg=93)
    macd = _flat_macd(50, 1.0)
    for idx in range(0, 6):
        macd[idx].hist = 10

    divergences = build_divergences(segments, [pivot], macd)
    buy_signals, _ = build_signals(candles, segments, [pivot], divergences)

    kinds = sorted({signal.kind for signal in buy_signals})
    assert "second" in kinds
    assert "first" in kinds
    second_buys = [s for s in buy_signals if s.kind == "second"]
    assert len(second_buys) == 1
    assert second_buys[0].price == 78
    assert second_buys[0].evidence is not None


def test_third_buy_signal_requires_pullback_above_pivot() -> None:
    from app.core.models import Direction, Pivot, Segment

    candles = [_candle(idx, 90 + idx, 80 + idx) for idx in range(50)]
    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=80, end_price=92, direction=Direction.UP),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=92, end_price=85, direction=Direction.DOWN),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=85, end_price=93, direction=Direction.UP),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=93, end_price=86, direction=Direction.DOWN),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=86, end_price=105, direction=Direction.UP),
        Segment(start_bi=10, end_bi=12, start_idx=25, end_idx=30, start_price=105, end_price=96, direction=Direction.DOWN),
        Segment(start_bi=12, end_bi=14, start_idx=30, end_idx=35, start_price=96, end_price=108, direction=Direction.UP),
    ]
    pivot = Pivot(start_bi=1, end_bi=3, start_idx=5, end_idx=20, zd=85, zg=93)
    macd = _flat_macd(50, 1.0)
    for idx in range(0, 6):
        macd[idx].hist = 10

    divergences = build_divergences(segments, [pivot], macd)
    buy_signals, sell_signals = build_signals(candles, segments, [pivot], divergences)

    assert [signal.kind for signal in sell_signals] == ["first"]
    assert [signal.kind for signal in buy_signals] == ["third"]


def test_shallow_leave_standalone_third_emits_third_class_buy() -> None:
    from app.core.models import Direction, Pivot, Segment

    candles = [_candle(idx, 90 + idx, 80 + idx) for idx in range(50)]
    segments = [
        Segment(start_bi=0, end_bi=2, start_idx=0, end_idx=5, start_price=80, end_price=92, direction=Direction.UP),
        Segment(start_bi=2, end_bi=4, start_idx=5, end_idx=10, start_price=92, end_price=85, direction=Direction.DOWN),
        Segment(start_bi=4, end_bi=6, start_idx=10, end_idx=15, start_price=85, end_price=93, direction=Direction.UP),
        Segment(start_bi=6, end_bi=8, start_idx=15, end_idx=20, start_price=93, end_price=86, direction=Direction.DOWN),
        Segment(start_bi=8, end_bi=10, start_idx=20, end_idx=25, start_price=86, end_price=93.5, direction=Direction.UP),
        Segment(start_bi=10, end_bi=12, start_idx=25, end_idx=30, start_price=93.5, end_price=93.4, direction=Direction.DOWN),
        Segment(start_bi=12, end_bi=14, start_idx=30, end_idx=35, start_price=93.4, end_price=94, direction=Direction.UP),
    ]
    pivot = Pivot(start_bi=1, end_bi=3, start_idx=5, end_idx=20, zd=85, zg=93)
    macd = _flat_macd(50, 1.0)
    for idx in range(0, 6):
        macd[idx].hist = 10

    divergences = build_divergences(segments, [pivot], macd)
    buy_signals, _ = build_signals(candles, segments, [pivot], divergences)

    kinds = {s.kind for s in buy_signals}
    assert "third_class" in kinds
    shallow = [s for s in buy_signals if s.kind == "third_class" and s.evidence and "中枢#0" in s.evidence]
    assert len(shallow) >= 1


def test_active_stroke_tracks_unconfirmed_move_after_last_confirmed_bi() -> None:
    from app.core.models import Direction, Stroke

    candles = [
        _candle(0, 12, 10),
        _candle(1, 11, 8),
        _candle(2, 10, 7),
        _candle(3, 12, 9),
        _candle(4, 14, 10),
    ]
    strokes = [
        Stroke(start_idx=0, end_idx=2, start_price=12, end_price=7, direction=Direction.DOWN),
    ]

    active = build_active_stroke(candles, strokes)

    assert active is not None
    assert active.direction == Direction.UP
    assert active.start_idx == 2
    assert active.end_idx == 4
    assert active.end_price == 14


def test_active_stroke_ignores_tiny_noise_move() -> None:
    from app.core.models import Direction, Stroke

    candles = [
        _candle(0, 10.2, 9.8),
        _candle(1, 11.5, 10.8),
    ]
    strokes = [
        Stroke(start_idx=0, end_idx=0, start_price=20, end_price=10, direction=Direction.DOWN),
    ]

    assert build_active_stroke(candles, strokes) is None


def test_active_stroke_uses_norm_index_and_candle_high_for_extreme() -> None:
    """未完成笔的端点须落在合并 K 线数组下标上（与 kline_data 对齐）；极值取自 high/low，与 high_idx 源编号无关。"""
    from app.core.models import Direction, Stroke

    normalized_candles = [
        _candle(2, 10, 7),
        Candle(
            open_time=4,
            time="t4",
            open=11,
            high=14,
            low=10,
            close=12,
            volume=2,
            source_idx=4,
            high_idx=3,
            low_idx=4,
        ),
    ]
    strokes = [
        Stroke(
            start_idx=0,
            end_idx=0,
            norm_start_idx=0,
            norm_end_idx=0,
            start_price=12,
            end_price=7,
            direction=Direction.DOWN,
        ),
    ]

    active = build_active_stroke(normalized_candles, strokes)

    assert active is not None
    assert active.start_idx == 0
    assert active.end_idx == 1
    assert active.norm_end_idx == 1
    assert active.end_price == 14


def test_t1p_buy_without_bi_zhongshu() -> None:
    from app.core.models import Stroke

    strokes = [
        Stroke(start_idx=0, end_idx=5, start_price=100, end_price=70, direction=Direction.DOWN),
        Stroke(start_idx=5, end_idx=8, start_price=70, end_price=85, direction=Direction.UP),
        Stroke(start_idx=8, end_idx=12, start_price=85, end_price=73, direction=Direction.DOWN),
    ]
    macd = _flat_macd(25, 1.0)
    for i in range(0, 6):
        macd[i].hist = 10.0
    for i in range(8, 13):
        macd[i].hist = 1.0
    candles = [_candle(i, 100 - i * 0.5, 90 - i * 0.5) for i in range(25)]
    buy, sell = build_t1p_pan_signals(candles, strokes, macd)
    assert sell == []
    assert len(buy) == 1
    assert buy[0].side == SignalSide.BUY
    assert "T1P" in buy[0].description
