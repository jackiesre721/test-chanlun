"""进阶缠论语境：多级别区间套、a+A+b+B+c、Zn、笔停顿、缺口、线段走势段（时间对齐）与走势类型/跨级递归（见 `trend_type_segment`）。"""

from __future__ import annotations

from typing import Optional

from app.core.models import (
    AbcDecomposition,
    AbcPart,
    Candle,
    ChanAdvancedContext,
    Direction,
    GapStat,
    NestedIntervalAnalysis,
    IntervalNestSlice,
    Pivot,
    Segment,
    SegmentTrendRun,
    Stroke,
)
from app.services.indicators import count_candle_gaps_in_range
from app.services.lines_form import analyze_lines_form
from app.services.trend_type_segment import (
    TREND_RULE_TABLE_ID,
    build_trend_recursion_summary,
    classify_segment_trend_run,
)

NESTED_ALIGNMENT_RULE_ID = "higher_norm_half_open_to_base_norm_index_v1"


def _stroke_overlaps_index_range(s: Stroke, lo: int, hi: int) -> bool:
    s_lo = min(s.start_idx, s.end_idx)
    s_hi = max(s.start_idx, s.end_idx)
    return not (s_hi < lo or s_lo > hi)


def _pivot_overlaps_index_range(p: Pivot, lo: int, hi: int) -> bool:
    return not (p.end_idx < lo or p.start_idx > hi)


def build_nested_interval_analysis(
    *,
    base_interval: str,
    candles: list[Candle],
    bis: list[Stroke],
    bi_pivots: list[Pivot],
    higher_interval: Optional[str],
    higher_strokes: list[Stroke],
    max_slices: int = 5,
) -> Optional[NestedIntervalAnalysis]:
    if not higher_interval or not higher_strokes:
        return None
    tail = higher_strokes[-max_slices:]
    base = len(higher_strokes) - len(tail)
    slices: list[IntervalNestSlice] = []
    for local_i, h in enumerate(tail):
        hidx = base + local_i
        lo = min(h.start_idx, h.end_idx)
        hi = max(h.start_idx, h.end_idx)
        sub_bis = [s for s in bis if _stroke_overlaps_index_range(s, lo, hi)]
        sub_pivots = [p for p in bi_pivots if p.level == "bi" and _pivot_overlaps_index_range(p, lo, hi)]
        lf = analyze_lines_form(sub_bis, sub_pivots)
        dir_zh = "上" if h.direction == Direction.UP else "下"
        bot_lo = candles[lo].open_time if candles and 0 <= lo < len(candles) else None
        bot_hi = candles[hi].open_time if candles and 0 <= hi < len(candles) else None
        hint = (
            f"上级{higher_interval}笔#{hidx}（{dir_zh}）→本级标准化K index[{lo}–{hi}]"
            f"（open_time {bot_lo}–{bot_hi}）"
            f"，含{len(sub_bis)}笔；形态 {lf.primary}。"
            if bot_lo is not None and bot_hi is not None
            else (
                f"上级{higher_interval}笔#{hidx}（{dir_zh}）→本级K[{lo}–{hi}]，"
                f"含{len(sub_bis)}笔；形态 {lf.primary}。"
            )
        )
        slices.append(
            IntervalNestSlice(
                higher_stroke_index=hidx,
                higher_direction=h.direction.value,
                candle_index_lo=lo,
                candle_index_hi=hi,
                base_open_time_lo=bot_lo,
                base_open_time_hi=bot_hi,
                higher_bar_index_lo=h.higher_origin_bar_lo,
                higher_bar_index_hi=h.higher_origin_bar_hi,
                higher_open_time_lo=h.higher_origin_open_time_lo,
                higher_open_time_hi=h.higher_origin_open_time_hi,
                sub_stroke_count=len(sub_bis),
                lines_form_primary=lf.primary,
                lines_form_detail_zh=lf.detail_zh,
                bi_pivot_count=len(sub_pivots),
                hint_zh=hint,
            )
        )
    summary = (
        f"已将上级 {higher_interval} 最近 {len(slices)} 笔按规则 "
        f"「{NESTED_ALIGNMENT_RULE_ID}」映射到本级 {base_interval} 标准化 K："
        f"上级 bar 的 open_time 半开区间落到本级 bar 上，再取本级笔与中枢子集做形态摘要。"
    )
    return NestedIntervalAnalysis(
        higher_interval=higher_interval,
        base_interval=base_interval,
        slices=slices,
        summary_zh=summary,
        alignment_rule_id=NESTED_ALIGNMENT_RULE_ID,
        time_axis="open_time_ms",
    )


def build_abc_decomposition(strokes: list[Stroke], bi_pivots: list[Pivot]) -> Optional[AbcDecomposition]:
    bi_only = [p for p in bi_pivots if p.level == "bi"]
    if len(bi_only) < 2:
        return None
    p0, p1 = bi_only[-2], bi_only[-1]
    stacked = p0.zg < p1.zd or p0.zd > p1.zg
    if not stacked:
        return None
    parts: list[AbcPart] = []
    if p0.start_bi > 0:
        parts.append(AbcPart(label="a", from_bi=0, to_bi=p0.start_bi - 1))
    parts.append(AbcPart(label="A", from_bi=p0.start_bi, to_bi=p0.end_bi))
    if p0.end_bi + 1 <= p1.start_bi - 1:
        parts.append(AbcPart(label="b", from_bi=p0.end_bi + 1, to_bi=p1.start_bi - 1))
    parts.append(AbcPart(label="B", from_bi=p1.start_bi, to_bi=p1.end_bi))
    if p1.end_bi + 1 <= len(strokes) - 1:
        parts.append(AbcPart(label="c", from_bi=p1.end_bi + 1, to_bi=len(strokes) - 1))
    return AbcDecomposition(
        parts=parts,
        note_zh="按最近两个价域分离的笔中枢粗分 a–A–b–B–c（算法近似，需结合走势人工复核）。",
    )


def build_segment_trend_runs(
    segments: list[Segment],
    *,
    segment_engine: str = "legacy",
    segment_pivots: Optional[list[Pivot]] = None,
) -> list[SegmentTrendRun]:
    if not segments:
        return []
    sp = [p for p in (segment_pivots or []) if p.level == "segment"]
    runs: list[SegmentTrendRun] = []
    start = 0
    merge_rule = f"contiguous_same_direction_segments_v1;segment_engine={segment_engine}"
    for i in range(1, len(segments) + 1):
        if i == len(segments) or segments[i].direction != segments[start].direction:
            block = segments[start:i]
            rh = max(max(s.start_price, s.end_price) for s in block)
            rl = min(min(s.start_price, s.end_price) for s in block)
            nseg = i - start
            direction = segments[start].direction
            code, note = classify_segment_trend_run(start, i - 1, direction, nseg, sp)
            runs.append(
                SegmentTrendRun(
                    start_seg_index=start,
                    end_seg_index=i - 1,
                    direction=direction.value,
                    segment_count=nseg,
                    run_high=rh,
                    run_low=rl,
                    level="segment",
                    merge_rule=merge_rule,
                    schema_version="chanlan-seg-trend-run-2",
                    trend_type_code=code,
                    trend_type_note_zh=note,
                    trend_rule_table_id=TREND_RULE_TABLE_ID,
                    segment_engine=segment_engine,
                )
            )
            start = i
    return runs


def _zn_from_last_bi_pivot(bi_pivots: list[Pivot]) -> tuple[Optional[float], Optional[str]]:
    bi_only = [p for p in bi_pivots if p.level == "bi"]
    if not bi_only:
        return None, None
    last = bi_only[-1]
    mid = (last.zg + last.zd) / 2.0
    note = f"最近笔中枢 Zn≈(ZG+ZD)/2 = {mid:.6g}（中枢 index 末段 {last.start_idx}–{last.end_idx}）。"
    return mid, note


def build_bi_pause_hint(candles: list[Candle], bis: list[Stroke]) -> Optional[str]:
    if len(candles) < 2 or not bis:
        return None
    last = bis[-1]
    lc = candles[-1]
    if last.direction == Direction.UP:
        if lc.close < lc.open and lc.close < last.start_price:
            return (
                "末根为阴线且收盘低于最近确认向上笔的起点价，接近「笔停顿」语境（对照用，非确认信号）。"
            )
    if last.direction == Direction.DOWN:
        if lc.close > lc.open and lc.close > last.start_price:
            return (
                "末根为阳线且收盘高于最近确认向下笔的起点价，接近「笔停顿」语境（对照用，非确认信号）。"
            )
    return None


def build_gap_stat_last_bi(candles: list[Candle], bis: list[Stroke]) -> Optional[GapStat]:
    if not bis or not candles:
        return None
    last_i = len(bis) - 1
    s = bis[last_i]
    lo = min(s.start_idx, s.end_idx)
    hi = max(s.start_idx, s.end_idx)
    up_g, dn_g = count_candle_gaps_in_range(candles, lo, hi)
    return GapStat(
        stroke_bi_index=last_i,
        candle_lo=lo,
        candle_hi=hi,
        up_gaps=up_g,
        down_gaps=dn_g,
    )


def build_chan_advanced_context(
    *,
    base_interval: str,
    candles: list[Candle],
    bis: list[Stroke],
    bi_pivots: list[Pivot],
    segments: list[Segment],
    segment_pivots: list[Pivot],
    higher_interval: Optional[str],
    higher_strokes: list[Stroke],
    segment_engine: str = "legacy",
) -> ChanAdvancedContext:
    nested = build_nested_interval_analysis(
        base_interval=base_interval,
        candles=candles,
        bis=bis,
        bi_pivots=bi_pivots,
        higher_interval=higher_interval,
        higher_strokes=higher_strokes,
    )
    abc = build_abc_decomposition(bis, bi_pivots)
    runs = build_segment_trend_runs(
        segments, segment_engine=segment_engine, segment_pivots=segment_pivots
    )
    trend_recursion = build_trend_recursion_summary(
        nested=nested,
        runs=runs,
        higher_interval=higher_interval,
    )
    zn_mid, zn_note = _zn_from_last_bi_pivot(bi_pivots)
    pause = build_bi_pause_hint(candles, bis)
    gap = build_gap_stat_last_bi(candles, bis)
    return ChanAdvancedContext(
        higher_interval=higher_interval,
        nested_interval=nested,
        abc_decomposition=abc,
        segment_trend_runs=runs,
        trend_recursion=trend_recursion,
        zn_last_bi_mid=zn_mid,
        zn_note_zh=zn_note,
        bi_pause_hint=pause,
        gap_last_bi=gap,
    )
