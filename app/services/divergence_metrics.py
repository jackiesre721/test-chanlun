"""背驰/力度标量：将多种算法统一为「进入段 vs 离开段」可比能源（自研实现）。"""

from __future__ import annotations

from typing import Union

from app.core.models import Candle, MacdPoint, Segment, Stroke
from app.services.indicators import macd_area
from app.services.macd_geometry import (
    macd_histogram_hump_energy,
    movement_hist_peak_max,
    movement_price_slope_per_bar,
)

Movement = Union[Stroke, Segment]

# 与对照表对齐的算法集合；either_loose 对该集合逐项 OR。
DIVERGENCE_METRIC_ALGOS: tuple[str, ...] = (
    "area",
    "full_area",
    "hump",
    "peak",
    "dif_range",
    "slope",
    "price_amp",
    "volume_sum",
    "amount_proxy",
    "volume_avg",
    "rsi_range",
)


def _idx_range(m: Movement) -> tuple[int, int]:
    lo = max(0, min(m.start_idx, m.end_idx))
    hi = max(m.start_idx, m.end_idx)
    return lo, hi


def _rsi_wilder_sub(closes: list[float], period: int = 14) -> list[float]:
    if len(closes) < period + 1 or period < 2:
        return []
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    out: list[float] = []

    def _r(ag_: float, al_: float) -> float:
        if al_ < 1e-18:
            return 100.0
        rs = ag_ / al_
        return 100.0 - (100.0 / (1.0 + rs))

    out.append(_r(ag, al))
    for i in range(period, len(deltas)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        out.append(_r(ag, al))
    return out


def movement_metric_scalar(
    algo: str,
    macd_points: list[MacdPoint],
    candles: list[Candle],
    m: Movement,
) -> float:
    lo, hi = _idx_range(m)
    if hi < lo or not macd_points:
        return 0.0

    if algo == "area":
        return macd_area(macd_points, m.start_idx, m.end_idx)
    if algo == "full_area":
        lo_i = max(0, min(m.start_idx, m.end_idx))
        hi_i = min(len(macd_points) - 1, max(m.start_idx, m.end_idx))
        if hi_i < lo_i:
            return 0.0
        return abs(sum(macd_points[i].hist for i in range(lo_i, hi_i + 1)))
    if algo == "hump":
        return macd_histogram_hump_energy(macd_points, m.start_idx, m.end_idx)
    if algo == "peak":
        return movement_hist_peak_max(macd_points, m.start_idx, m.end_idx)
    if algo == "dif_range":
        lo_i = max(0, min(m.start_idx, m.end_idx))
        hi_i = min(len(macd_points) - 1, max(m.start_idx, m.end_idx))
        if hi_i < lo_i:
            return 0.0
        mx = max(macd_points[i].dif for i in range(lo_i, hi_i + 1))
        mn = min(macd_points[i].dif for i in range(lo_i, hi_i + 1))
        return max(0.0, mx - mn)
    if algo == "slope":
        return movement_price_slope_per_bar(m.start_idx, m.end_idx, m.start_price, m.end_price)

    if not candles:
        return 0.0
    lo_c = max(0, min(lo, len(candles) - 1))
    hi_c = min(len(candles) - 1, hi)
    if lo_c > hi_c:
        return 0.0

    if algo == "volume_sum":
        return float(sum(candles[i].volume for i in range(lo_c, hi_c + 1)))
    if algo == "volume_avg":
        n = hi_c - lo_c + 1
        return float(sum(candles[i].volume for i in range(lo_c, hi_c + 1))) / max(n, 1)
    if algo == "amount_proxy":
        return float(sum(candles[i].close * candles[i].volume for i in range(lo_c, hi_c + 1)))
    if algo == "price_amp":
        highs = [candles[i].high for i in range(lo_c, hi_c + 1)]
        lows = [candles[i].low for i in range(lo_c, hi_c + 1)]
        return max(0.0, max(highs) - min(lows)) if highs else 0.0
    if algo == "rsi_range":
        sub_closes = [candles[i].close for i in range(lo_c, hi_c + 1)]
        rsi_vals = _rsi_wilder_sub(sub_closes, 14)
        if len(rsi_vals) < 2:
            return 0.0
        return max(rsi_vals) - min(rsi_vals)

    return 0.0


def divergence_pair_weakens(
    algo: str,
    macd_points: list[MacdPoint],
    candles: list[Candle],
    entry: Movement,
    leaving: Movement,
    ratio_limit: float,
) -> bool:
    ev = movement_metric_scalar(algo, macd_points, candles, entry)
    lv = movement_metric_scalar(algo, macd_points, candles, leaving)
    return ev > 1e-18 and lv / ev < ratio_limit


def divergence_either_loose_weakens(
    macd_points: list[MacdPoint],
    candles: list[Candle],
    entry: Movement,
    leaving: Movement,
    ratio_limit: float,
) -> bool:
    for algo in DIVERGENCE_METRIC_ALGOS:
        if divergence_pair_weakens(algo, macd_points, candles, entry, leaving, ratio_limit):
            return True
    return False


def divergence_multi_weakens(
    algos: tuple[str, ...],
    macd_points: list[MacdPoint],
    candles: list[Candle],
    entry: Movement,
    leaving: Movement,
    ratio_limit: float,
    *,
    mode: str,
) -> bool:
    ok_flags = [
        divergence_pair_weakens(a, macd_points, candles, entry, leaving, ratio_limit) for a in algos
    ]
    if mode == "all":
        return bool(ok_flags) and all(ok_flags)
    return any(ok_flags) if ok_flags else False
