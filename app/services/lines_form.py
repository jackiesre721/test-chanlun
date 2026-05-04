"""线段/笔序列的形态粗分类（对照 chanlun-pro LinesForm 思路的 MVP 实现）。"""

from __future__ import annotations

from app.core.models import Direction, LinesFormSummary, Pivot, Stroke
from app.services.chan_engine import _strokes_have_overlap


def analyze_lines_form(strokes: list[Stroke], bi_pivots: list[Pivot]) -> LinesFormSummary:
    """基于笔序列与笔中枢的轻量形态标签，供 UI / 后续区间套扩展。"""
    if len(strokes) < 3:
        return LinesFormSummary(
            primary="insufficient",
            detail_zh="确认笔少于 3，不足以做形态分类。",
            bi_pivot_count=len(bi_pivots),
        )

    triple_overlap = any(
        _strokes_have_overlap(strokes[i : i + 3]) for i in range(len(strokes) - 2)
    )
    n_bi = len(bi_pivots)

    stacked = False
    if n_bi >= 2:
        prev, cur = bi_pivots[-2], bi_pivots[-1]
        stacked = prev.zg < cur.zd or prev.zd > cur.zg

    first = strokes[0]
    last = strokes[-1]
    net_up = last.end_price > first.start_price
    net_dn = last.end_price < first.start_price

    up_count = sum(1 for s in strokes if s.direction == Direction.UP)
    ratio_up = up_count / len(strokes)

    if stacked and n_bi >= 2:
        return LinesFormSummary(
            primary="trend",
            detail_zh="多个笔中枢价域呈阶梯堆叠，偏趋势类走势（可结合区间套继续细化）。",
            has_three_stroke_overlap=triple_overlap,
            bi_pivot_count=n_bi,
            abc_hint="观察到多中枢阶梯，可对照 a+A+b+B+c 式走势分解（本字段为提示，非自动判定）。",
        )
    if n_bi >= 1 and 0.35 <= ratio_up <= 0.65 and len(strokes) >= 6:
        primary = "zpan"
        detail = "存在笔中枢且上下笔比例接近，偏盘整震荡语境。"
    elif triple_overlap and n_bi == 0 and len(strokes) <= 8:
        primary = "three_bi"
        detail = "出现三笔重叠窗口，尚未形成稳定笔中枢，多为局部三笔结构。"
    elif (net_up and ratio_up >= 0.55) or (net_dn and ratio_up <= 0.45):
        primary = "quasi_trend"
        detail = "端点净方向与笔向比例偏一边，类趋势倾向（未必已形成标准趋势中枢）。"
    elif triple_overlap:
        primary = "mixed"
        detail = "有三笔重叠但中枢与方向信号不一致，标为混合待复核。"
    else:
        primary = "mixed"
        detail = "未落入上述典型桶，标为混合。"

    return LinesFormSummary(
        primary=primary,
        detail_zh=detail,
        has_three_stroke_overlap=triple_overlap,
        bi_pivot_count=n_bi,
        abc_hint=None,
    )
