"""线段级走势类型：以线段中枢为「走势中枢」代理，用价域堆叠/重叠 + 段向一致性判定。

规则表 `seg-zs-stack-overlap-v1`（可审计）：
- 在「同向连续线段合并」窗口内，收集与之相交的 `level=segment` 中枢；
- **上移堆叠**：存在相邻中枢满足 ZG_i < ZD_{i+1}（价域整体上移）→ 与向上段一致则判 **上涨走势**；
- **下移堆叠**：ZD_i > ZG_{i+1}** → 与向下段一致则判 **下跌走势**；
- 同时存在上移与下移堆叠 → **双向中枢震荡**；
- 段向与堆叠方向矛盾 → **级别/方向背离**；
- 多个中枢相交窗口但无上述阶梯 → **盘整走势**（中枢价域重叠震荡）；
- 单中枢窗口内多段同向延伸 → **中枢内走势延伸**；
- 无段中枢 → 多段同向 **方向延伸**，单段 **中性**。
"""

from __future__ import annotations

from typing import Optional

from app.core.models import (
    Direction,
    NestedIntervalAnalysis,
    Pivot,
    SegmentTrendRun,
    SegmentTrendTypeCode,
    TrendRecursionSummary,
)

TREND_RULE_TABLE_ID = "seg-zs-stack-overlap-v1"

_RECURSION_RULE_VERSION = "cross-level-lines-form-vs-seg-run-v1"


def _pivots_in_segment_window(
    segment_pivots: list[Pivot], seg_lo: int, seg_hi: int
) -> list[Pivot]:
    out = [
        p
        for p in segment_pivots
        if p.level == "segment" and not (p.end_bi < seg_lo or p.start_bi > seg_hi)
    ]
    return sorted(out, key=lambda p: p.start_bi)


def _has_stack_up(pivots: list[Pivot], eps: float = 1e-9) -> bool:
    for i in range(len(pivots) - 1):
        if pivots[i].zg + eps < pivots[i + 1].zd:
            return True
    return False


def _has_stack_down(pivots: list[Pivot], eps: float = 1e-9) -> bool:
    for i in range(len(pivots) - 1):
        if pivots[i].zd > pivots[i + 1].zg + eps:
            return True
    return False


def classify_segment_trend_run(
    seg_lo: int,
    seg_hi: int,
    direction: Direction,
    segment_count: int,
    segment_pivots: list[Pivot],
) -> tuple[SegmentTrendTypeCode, str]:
    pv = _pivots_in_segment_window(segment_pivots, seg_lo, seg_hi)
    if not pv:
        if segment_count >= 2:
            return "directional_extension", (
                "窗口内无线段中枢；同向线段合并为**方向延伸**（尚未形成走势中枢代理结构）。"
            )
        return "neutral_single_segment", "单线段且无相交线段中枢，走势类型标为中性。"

    su = _has_stack_up(pv)
    sd = _has_stack_down(pv)

    if su and sd:
        return "mixed_bidirectional_zs", (
            "窗口内线段中枢同时存在上移与下移堆叠，判为**中枢震荡/双向级别拉扯**，不宜单方向押注。"
        )

    if direction == Direction.UP and su:
        return "uptrend_zs_stacked", (
            "存在线段中枢**上移堆叠**（ZG_i<ZD_{i+1}）且与同向向上线段一致，判为**上涨走势**"
            "（以线段中枢为走势中枢代理，对应课文走势分解可审计实现）。"
        )
    if direction == Direction.DOWN and sd:
        return "downtrend_zs_stacked", (
            "存在线段中枢**下移堆叠**（ZD_i>ZG_{i+1}）且与同向向下线段一致，判为**下跌走势**（同上）。"
        )

    if direction == Direction.UP and sd and not su:
        return "mixed_counterstack", (
            "向上线段窗口内出现**下移堆叠**中枢而未形成上移堆叠，段向与中枢阶梯**背离**，按盘整/转折风险处理。"
        )
    if direction == Direction.DOWN and su and not sd:
        return "mixed_counterstack", (
            "向下线段窗口内出现**上移堆叠**中枢而未形成下移堆叠，段向与中枢阶梯**背离**。"
        )

    if len(pv) >= 2:
        return "consolidation_zs_overlap", (
            "多个线段中枢落入窗口但**无与段向一致的阶梯堆叠**，判为**盘整走势**（中枢价域重叠震荡语境）。"
        )

    if len(pv) == 1 and segment_count >= 2:
        return "trend_extension_in_zs", (
            "单一线段中枢与多根同向线段相交，判为**走势在同向中枢内延伸**（尚未走出新中枢阶梯）。"
        )

    return "neutral_single_segment", "单线段与至多一个相交中枢，结构信息不足，标为中性。"


def build_trend_recursion_summary(
    *,
    nested: Optional[NestedIntervalAnalysis],
    runs: list[SegmentTrendRun],
    higher_interval: Optional[str],
) -> TrendRecursionSummary:
    """上级区间套末片 `lines_form` 与本级末段 `trend_type_code` 的递归一致性（工程规则）。"""
    if not higher_interval:
        return TrendRecursionSummary(
            composite="insufficient_higher_data",
            note_zh="当前周期无上配置的上级 interval，不做跨级别递归对照。",
            higher_lines_form_primary=None,
            base_last_run_trend_code=None,
            rule_table_version=_RECURSION_RULE_VERSION,
        )

    if nested is None or not nested.slices:
        return TrendRecursionSummary(
            composite="insufficient_higher_data",
            note_zh="未能生成上级笔区间套（可能上级数据缺失）；跨级别递归对照跳过。",
            higher_lines_form_primary=None,
            base_last_run_trend_code=runs[-1].trend_type_code if runs else None,
            rule_table_version=_RECURSION_RULE_VERSION,
        )

    last_slice = nested.slices[-1]
    lf = last_slice.lines_form_primary
    last_run = runs[-1] if runs else None
    br: Optional[str] = last_run.trend_type_code if last_run else None

    comp = "partially_aligned"
    note = ""

    uptrend_codes = frozenset({"uptrend_zs_stacked", "trend_extension_in_zs", "directional_extension"})
    downtrend_codes = frozenset({"downtrend_zs_stacked", "trend_extension_in_zs", "directional_extension"})
    consol_codes = frozenset(
        {
            "consolidation_zs_overlap",
            "neutral_single_segment",
            "mixed_bidirectional_zs",
            "mixed_counterstack",
        }
    )

    lf_trendy = lf in ("trend", "quasi_trend")

    if lf_trendy and br in uptrend_codes and last_run and last_run.direction == "UP":
        comp, note = "aligned_uptrend", "上级末片为趋势/类趋势、本级末段为向上走势相关类型，递归上偏多一致。"
    elif lf_trendy and br in downtrend_codes and last_run and last_run.direction == "DOWN":
        comp, note = "aligned_downtrend", "上级末片趋势/类趋势与本级末段向下走势类型一致，递归上偏空一致。"
    elif lf in ("zpan", "mixed", "insufficient", "three_bi") and br in consol_codes:
        comp, note = "aligned_consolidation", "上级末片偏震荡与本级盘整/中性段类型一致，递归上震荡一致。"
    elif lf_trendy and br in consol_codes:
        comp, note = "cross_level_divergent", "上级末片偏趋势而本级末段偏盘整/背离中枢，级别语境打架，宜降杠杆或等待确认。"
    elif lf in ("zpan", "mixed") and br in uptrend_codes.union(downtrend_codes) - {"neutral_single_segment"}:
        comp, note = "cross_level_divergent", "上级偏震荡而本级出现趋势型堆叠/延伸，可能与更大级别盘整嵌套，注意假突破。"
    else:
        comp, note = "partially_aligned", "上下级形态未落入强一致/强背离桶，标为部分一致，请结合价位与量能。"

    return TrendRecursionSummary(
        composite=comp,
        note_zh=note,
        higher_lines_form_primary=lf,
        base_last_run_trend_code=br,
        rule_table_version=_RECURSION_RULE_VERSION,
    )
