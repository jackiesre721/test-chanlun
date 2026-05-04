"""中枢「对称」粗判：以 [ZD,ZG] 中轴为界，看区间内收盘价落在上下侧的根数平衡度（启发式）。"""

from __future__ import annotations

from app.core.models import Candle, Pivot


def pivot_symmetry_balance(candles: list[Candle], pivot: Pivot) -> float:
    """返回 0~1，越接近 1 表示上下侧根数越接近（无任何有效柱时 0.5）。"""
    if not candles:
        return 0.5
    lo = max(0, min(pivot.start_idx, pivot.end_idx))
    hi = min(len(candles) - 1, max(pivot.start_idx, pivot.end_idx))
    mid = (pivot.zg + pivot.zd) / 2
    above = 0
    below = 0
    for i in range(lo, hi + 1):
        c = candles[i].close
        if c > mid + 1e-12:
            above += 1
        elif c < mid - 1e-12:
            below += 1
    total = above + below
    if total <= 0:
        return 0.5
    return float(min(above, below) / max(above, below, 1))


def is_symmetry_zs(candles: list[Candle], pivot: Pivot, *, min_balance: float = 0.38) -> bool:
    return pivot_symmetry_balance(candles, pivot) >= min_balance


def hydrate_pivot_symmetry(pivots: list[Pivot], candles: list[Candle], *, min_balance: float = 0.38) -> list[Pivot]:
    out: list[Pivot] = []
    for p in pivots:
        bal = pivot_symmetry_balance(candles, p)
        out.append(
            p.model_copy(update={"symmetry_balance": bal, "symmetry_zs": bal >= min_balance}),
        )
    return out
