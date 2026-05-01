from app.core.models import Candle
from app.services.chan_engine import (
    build_active_stroke,
    build_divergences,
    build_pivots,
    build_segment_pivots,
    build_segments,
    build_signals,
    build_strokes,
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
    assert pivots[0].start_bi == 1
    assert pivots[0].end_bi == 4
    assert pivots[0].zd == 16
    assert pivots[0].zg == 17


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

    assert [signal.kind for signal in buy_signals] == ["first", "second"]
    assert buy_signals[1].price == 78


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


def test_active_stroke_uses_extreme_source_index_from_normalized_candle() -> None:
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
            end_idx=2,
            norm_start_idx=0,
            norm_end_idx=0,
            start_price=12,
            end_price=7,
            direction=Direction.DOWN,
        ),
    ]

    active = build_active_stroke(normalized_candles, strokes)

    assert active is not None
    assert active.start_idx == 2
    assert active.end_idx == 3
    assert active.norm_end_idx == 1
    assert active.end_price == 14
