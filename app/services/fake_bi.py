"""FakeBI：单笔内部「次级别」笔链（由内部确认分型递归出短笔，不切周期近似）。"""

from __future__ import annotations

from app.core.models import Candle, Direction, FakeBiStroke, Fractal, Stroke
from app.services.chan_engine import STRICT_MIN_STROKE_SPAN, build_strokes


def build_fake_bis(
    strokes: list[Stroke],
    fractals: list[Fractal],
    candles: list[Candle],
    *,
    min_gap: int | None = None,
) -> list[FakeBiStroke]:
    """对每笔，取 norm 索引开区间内的确认分型，用更小的最小跨度生成虚拟笔。"""
    gap = max(2, (min_gap or max(2, STRICT_MIN_STROKE_SPAN // 2)))
    confirmed = [f for f in fractals if f.confirmed]
    out: list[FakeBiStroke] = []
    for pidx, st in enumerate(strokes):
        ns = st.norm_start_idx
        ne = st.norm_end_idx
        if ns is None or ne is None:
            continue
        lo = min(ns, ne)
        hi = max(ns, ne)
        inner = [f for f in confirmed if lo < f.norm_idx < hi]
        if len(inner) < 2:
            continue
        mini = build_strokes(inner, min_gap=gap, candles=candles)
        for mb in mini:
            out.append(
                FakeBiStroke(
                    parent_bi_index=pidx,
                    start_idx=mb.start_idx,
                    end_idx=mb.end_idx,
                    norm_start_idx=mb.norm_start_idx,
                    norm_end_idx=mb.norm_end_idx,
                    start_price=mb.start_price,
                    end_price=mb.end_price,
                    direction=mb.direction,
                )
            )
    return out
