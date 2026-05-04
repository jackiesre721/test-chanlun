"""MACD 序列上的几何度量（与本项目背驰判定配套，独立实现）。

驼峰：hist 同号连续段视为一根「柱子丛」，取该段内 |hist| 的最大值作为一个驼峰高度；
多根驼峰的高度之和作为区段上的「驼峰能量」，用于与柱面积互补的比较方式。
"""

from __future__ import annotations

from app.core.models import MacdPoint


def macd_histogram_hump_energy(points: list[MacdPoint], start_idx: int, end_idx: int) -> float:
    """同向柱丛的峰值之和（每个连续同号段只贡献一个峰值）。"""
    if not points:
        return 0.0
    lo = max(0, min(start_idx, end_idx))
    hi = min(len(points) - 1, max(start_idx, end_idx))
    if lo > hi:
        return 0.0
    energy = 0.0
    i = lo
    while i <= hi:
        h = points[i].hist
        if abs(h) < 1e-18:
            i += 1
            continue
        sign = 1 if h > 0 else -1
        peak = abs(h)
        i += 1
        while i <= hi:
            h2 = points[i].hist
            if abs(h2) < 1e-18:
                break
            s2 = 1 if h2 > 0 else -1
            if s2 != sign:
                break
            peak = max(peak, abs(h2))
            i += 1
        energy += peak
    return energy


def dif_dea_cross_zero_in_range(points: list[MacdPoint], start_idx: int, end_idx: int, *, abs_eps: float) -> bool:
    """区段内 DIF 是否贴近 0 或发生穿越（相对零轴）。"""
    if not points or abs_eps < 0:
        return False
    lo = max(0, min(start_idx, end_idx))
    hi = min(len(points) - 1, max(start_idx, end_idx))
    if lo > hi:
        return False
    prev = 0
    for i in range(lo, hi + 1):
        d = points[i].dif
        if abs(d) <= abs_eps:
            return True
        s = 1 if d > 0 else -1
        if prev != 0 and s != prev:
            return True
        prev = s
    return False


def macd_abs_peaks_hist_dif_dea(
    points: list[MacdPoint], start_idx: int, end_idx: int
) -> tuple[float, float, float]:
    """区段内 |hist|、|dif|、|dea| 的峰值（独立统计，供背驰力度闸门使用）。"""
    if not points:
        return 0.0, 0.0, 0.0
    lo = max(0, min(start_idx, end_idx))
    hi = min(len(points) - 1, max(start_idx, end_idx))
    if lo > hi:
        return 0.0, 0.0, 0.0
    mh = md = me = 0.0
    for i in range(lo, hi + 1):
        p = points[i]
        mh = max(mh, abs(p.hist))
        md = max(md, abs(p.dif))
        me = max(me, abs(p.dea))
    return mh, md, me


def movement_hist_peak_max(points: list[MacdPoint], start_idx: int, end_idx: int) -> float:
    """区段内 MACD 柱 |hist| 的最大值（PEAK 力度）。"""
    mh, _, _ = macd_abs_peaks_hist_dif_dea(points, start_idx, end_idx)
    return mh


def movement_price_slope_per_bar(
    start_idx: int, end_idx: float, start_price: float, end_price: float
) -> float:
    """|价变| / 含 K 根数，用于两段「速度」归一比较。"""
    lo = int(max(0, min(start_idx, int(end_idx))))
    hi = int(max(start_idx, int(end_idx)))
    n = hi - lo + 1
    if n < 1:
        return 0.0
    return abs(float(end_price) - float(start_price)) / float(n)


def peaks_shrink_vs_reference(
    points: list[MacdPoint],
    ref: tuple[float, float, float],
    seg: tuple[int, int],
    *,
    max_ratio: float,
    require_dea: bool,
) -> bool:
    """离开段三类峰值相对参考段是否同步减弱（乘 max_ratio）。"""
    lh, ld, le = macd_abs_peaks_hist_dif_dea(points, seg[0], seg[1])
    rh, rd, re = ref
    eps = 1e-12
    r = max_ratio
    ok_h = lh <= rh * r + eps if rh > eps else True
    ok_d = ld <= rd * r + eps if rd > eps else True
    ok_e = le <= re * r + eps if re > eps else True
    if require_dea:
        return ok_h and ok_d and ok_e
    return ok_h and ok_d
