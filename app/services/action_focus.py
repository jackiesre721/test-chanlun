"""当下关注点：根据已计算的结构产出可展示语境（非交易指令）。"""

from __future__ import annotations

from typing import Literal, Optional

from app.core.models import (
    ActionFocus,
    ActionFocusActiveBi,
    ActionFocusPivotRef,
    ActionFocusPivotSlot,
    ActionFocusRecentDivergence,
    ActionFocusRecentSignal,
    Divergence,
    Pivot,
    Signal,
    Stroke,
)


def _recent_window_size(kline_count: int) -> int:
    return max(18, min(80, int(kline_count * 0.06)))


def _pick_reference_pivot(pivots: list[Pivot], last_idx: int) -> Optional[Pivot]:
    if not pivots:
        return None
    candidates = [p for p in pivots if last_idx >= p.start_idx and last_idx <= p.end_idx]
    if not candidates:
        return max(pivots, key=lambda p: p.end_idx)
    return max(candidates, key=lambda p: p.end_idx - p.start_idx)


def _pivot_to_ref(p: Pivot) -> ActionFocusPivotRef:
    return ActionFocusPivotRef(
        level=p.level,
        zd=p.zd,
        zg=p.zg,
        start_idx=p.start_idx,
        end_idx=p.end_idx,
    )


def _price_vs_pivot(price: float, pivot: Pivot) -> Literal["inside", "above", "below"]:
    if pivot.zd <= price <= pivot.zg:
        return "inside"
    if price > pivot.zg:
        return "above"
    return "below"


def _slot_for_pivots(pivots: list[Pivot], last_idx: int, price: float) -> ActionFocusPivotSlot:
    ref_p = _pick_reference_pivot(pivots, last_idx)
    if ref_p is None:
        return ActionFocusPivotSlot(relation="none", pivot=None)
    return ActionFocusPivotSlot(
        relation=_price_vs_pivot(price, ref_p),
        pivot=_pivot_to_ref(ref_p),
    )


def _latest_divergence_since(divergences: list[Divergence], since_idx: int) -> Optional[Divergence]:
    windowed = [d for d in divergences if d.idx >= since_idx]
    if not windowed:
        return None
    return max(windowed, key=lambda d: d.idx)


def _latest_signal_since(buy: list[Signal], sell: list[Signal], since_idx: int) -> Optional[Signal]:
    merged = [s for s in buy + sell if s.idx >= since_idx]
    if not merged:
        return None
    return max(merged, key=lambda s: s.idx)


def build_action_focus(
    *,
    current_price: float,
    last_bar_index: int,
    kline_count: int,
    zhongshus: list[Pivot],
    zhongshus_lv2: list[Pivot],
    active_bi: Optional[Stroke],
    divergences: list[Divergence],
    buy_signals: list[Signal],
    sell_signals: list[Signal],
) -> ActionFocus:
    recent_bars = _recent_window_size(kline_count) if kline_count else 1
    recent_since = last_bar_index - recent_bars

    active_bi_out: Optional[ActionFocusActiveBi] = None
    if active_bi is not None:
        active_bi_out = ActionFocusActiveBi(
            direction=active_bi.direction,
            start_price=active_bi.start_price,
            end_price=active_bi.end_price,
        )

    d_latest = _latest_divergence_since(divergences, recent_since)
    recent_div: Optional[ActionFocusRecentDivergence] = None
    if d_latest is not None:
        recent_div = ActionFocusRecentDivergence(
            level=d_latest.level,
            direction=d_latest.direction,
            idx=d_latest.idx,
            ratio=d_latest.ratio,
            structure_kind=d_latest.structure_kind,
        )
    elif divergences:
        d_fallback = max(divergences, key=lambda d: d.idx)
        recent_div = ActionFocusRecentDivergence(
            level=d_fallback.level,
            direction=d_fallback.direction,
            idx=d_fallback.idx,
            ratio=d_fallback.ratio,
            structure_kind=d_fallback.structure_kind,
        )
        recent_bars = max(recent_bars, last_bar_index - d_fallback.idx + 1)

    s_latest = _latest_signal_since(buy_signals, sell_signals, recent_since)
    recent_sig: Optional[ActionFocusRecentSignal] = None
    if s_latest is not None:
        recent_sig = ActionFocusRecentSignal(
            side=s_latest.side,
            kind=s_latest.kind,
            idx=s_latest.idx,
            time=s_latest.time,
            price=s_latest.price,
            stop_loss=s_latest.stop_loss,
            stop_loss_2=s_latest.stop_loss_2,
            take_profit_1=s_latest.take_profit_1,
            take_profit_2=s_latest.take_profit,
        )
    else:
        merged = buy_signals + sell_signals
        if merged:
            s_fallback = max(merged, key=lambda s: s.idx)
            recent_sig = ActionFocusRecentSignal(
                side=s_fallback.side,
                kind=s_fallback.kind,
                idx=s_fallback.idx,
                time=s_fallback.time,
                price=s_fallback.price,
                stop_loss=s_fallback.stop_loss,
                stop_loss_2=s_fallback.stop_loss_2,
                take_profit_1=s_fallback.take_profit_1,
                take_profit_2=s_fallback.take_profit,
            )
            recent_bars = max(recent_bars, last_bar_index - s_fallback.idx + 1)

    return ActionFocus(
        last_bar_index=last_bar_index,
        recent_window_bars=recent_bars,
        current_price=current_price,
        primary_pivot=_slot_for_pivots(zhongshus, last_bar_index, current_price),
        higher_pivot=_slot_for_pivots(zhongshus_lv2, last_bar_index, current_price),
        active_bi=active_bi_out,
        recent_divergence=recent_div,
        recent_signal=recent_sig,
    )
