"""线段中枢堆叠 → 走势类型判定与跨级别递归摘要。"""

from __future__ import annotations

from app.core.models import Direction, Pivot, SegmentTrendRun
from app.services.trend_type_segment import (
    build_trend_recursion_summary,
    classify_segment_trend_run,
)


def test_classify_uptrend_when_segment_pivots_stack_up() -> None:
    pivots = [
        Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=1, zd=10.0, zg=20.0, level="segment"),
        Pivot(start_bi=3, end_bi=5, start_idx=2, end_idx=3, zd=25.0, zg=35.0, level="segment"),
    ]
    code, _note = classify_segment_trend_run(0, 5, Direction.UP, 3, pivots)
    assert code == "uptrend_zs_stacked"


def test_classify_consolidation_when_two_pivots_not_stacked() -> None:
    pivots = [
        Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=1, zd=15.0, zg=28.0, level="segment"),
        Pivot(start_bi=3, end_bi=5, start_idx=2, end_idx=3, zd=18.0, zg=30.0, level="segment"),
    ]
    code, _note = classify_segment_trend_run(0, 5, Direction.UP, 3, pivots)
    assert code == "consolidation_zs_overlap"


def test_classify_mixed_counterstack_up_run_with_down_stack() -> None:
    pivots = [
        Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=1, zd=40.0, zg=50.0, level="segment"),
        Pivot(start_bi=3, end_bi=5, start_idx=2, end_idx=3, zd=25.0, zg=35.0, level="segment"),
    ]
    code, _note = classify_segment_trend_run(0, 5, Direction.UP, 3, pivots)
    assert code == "mixed_counterstack"


def test_recursion_aligned_uptrend() -> None:
    from app.core.models import IntervalNestSlice, NestedIntervalAnalysis

    nested = NestedIntervalAnalysis(
        higher_interval="15",
        base_interval="1",
        slices=[
            IntervalNestSlice(
                higher_stroke_index=0,
                higher_direction="UP",
                candle_index_lo=0,
                candle_index_hi=10,
                sub_stroke_count=0,
                lines_form_primary="trend",
            )
        ],
        summary_zh="",
    )
    runs = [
        SegmentTrendRun(
            start_seg_index=0,
            end_seg_index=1,
            direction="UP",
            segment_count=2,
            run_high=2.0,
            run_low=1.0,
            trend_type_code="uptrend_zs_stacked",
        )
    ]
    s = build_trend_recursion_summary(nested=nested, runs=runs, higher_interval="15")
    assert s.composite == "aligned_uptrend"


def test_recursion_cross_level_when_trend_vs_consolidation() -> None:
    from app.core.models import IntervalNestSlice, NestedIntervalAnalysis

    nested = NestedIntervalAnalysis(
        higher_interval="15",
        base_interval="1",
        slices=[
            IntervalNestSlice(
                higher_stroke_index=0,
                higher_direction="UP",
                candle_index_lo=0,
                candle_index_hi=10,
                sub_stroke_count=0,
                lines_form_primary="trend",
            )
        ],
        summary_zh="",
    )
    runs = [
        SegmentTrendRun(
            start_seg_index=0,
            end_seg_index=0,
            direction="DOWN",
            segment_count=1,
            run_high=2.0,
            run_low=1.0,
            trend_type_code="consolidation_zs_overlap",
        )
    ]
    s = build_trend_recursion_summary(nested=nested, runs=runs, higher_interval="15")
    assert s.composite == "cross_level_divergent"
