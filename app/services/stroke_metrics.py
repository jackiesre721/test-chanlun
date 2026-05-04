"""笔（原 Stroke）上的几何与统计量，供力度评估与 UI（自研，非拷贝第三方）。"""

from __future__ import annotations

import math

from app.core.models import Candle, Stroke


def _rsquared_linear(xs: list[int], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx < 1e-18 or syy < 1e-18:
        return 0.0
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    r = sxy / math.sqrt(sxx * syy)
    return float(max(0.0, min(1.0, r * r)))


def hydrate_stroke_metrics(strokes: list[Stroke], candles: list[Candle]) -> list[Stroke]:
    """用与笔索引一致的 K 线序列（通常为 normalize 后）填充 czsc 类比属性。"""
    if not strokes or not candles:
        return strokes
    out: list[Stroke] = []
    for s in strokes:
        lo = min(s.start_idx, s.end_idx)
        hi = max(s.start_idx, s.end_idx)
        lo = max(0, min(lo, len(candles) - 1))
        hi = max(0, min(hi, len(candles) - 1))
        if hi < lo:
            out.append(s)
            continue
        span_idx = hi - lo
        n_bars = span_idx + 1
        price_delta = s.end_price - s.start_price
        slope = price_delta / max(span_idx, 1)
        closes = [candles[i].close for i in range(lo, hi + 1)]
        vols = [candles[i].volume for i in range(lo, hi + 1)]
        power_vol = float(sum(vols))
        power_price = abs(price_delta)
        mid_px = max(abs(s.start_price), 1e-12)
        rel_move = price_delta / mid_px
        angle_deg = float(math.degrees(math.atan2(rel_move, 1.0)))
        hypotenuse = float(math.hypot(float(max(span_idx, 1)), abs(rel_move)))
        xs = list(range(lo, hi + 1))
        rsq_close = _rsquared_linear(xs, closes)
        acc: float | None = None
        if len(closes) >= 4:
            mid = len(closes) // 2
            run1 = max(mid - 1, 1)
            run2 = max(len(closes) - mid - 1, 1)
            s1 = (closes[mid - 1] - closes[0]) / run1
            s2 = (closes[-1] - closes[mid]) / run2
            acc = float(s2 - s1)
        mean_c = sum(closes) / len(closes)
        var = sum((c - mean_c) ** 2 for c in closes) / max(len(closes), 1)
        std = math.sqrt(var)
        power_snr = float(abs(price_delta) / (std + 1e-12))
        out.append(
            s.model_copy(
                update={
                    "length_bars": n_bars,
                    "price_change": float(price_delta),
                    "slope_per_bar": float(slope),
                    "angle_deg": angle_deg,
                    "hypotenuse": hypotenuse,
                    "power_price": float(power_price),
                    "power_volume": power_vol,
                    "rsq_close": float(rsq_close),
                    "acceleration": acc,
                    "power_snr": power_snr,
                }
            )
        )
    return out
