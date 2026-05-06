"""缠论几何流水线（笔、线段简化版、中枢、背驰、买卖点）。

与原文（`/Users/richie/chanlun_notes` 中整理的课文）对照时的**实现边界**：

- **K 线包含与分型**（62/65 课）：`normalize_candles` 顺序合并包含；`find_fractals` 在三根无包含 K 上取顶/底分型（顶：高中最高且**低也最高**；底：低最低且**高也最低**）。
- **笔**（62 课）：相邻顶底分型之间至少隔 `STRICT_MIN_STROKE_SPAN` 根标准化 K（保证顶底间有独立 K 线意义）。
- **线段**（67 课）：`CHANLAN_SEGMENT_ENGINE=strict67` 时走**标准特征序列**：先按线段方向做元素**非包含合并**，再在合并序列上找顶/底分型；**情形一**（分型一二元素区间重叠）直接结束；**情形二**（有缺口）需**第二特征序列**再出现同向分型才结束。未命中时仍回退 legacy 延伸。
- **线段中枢**：**连续三线段**的价位区间有重叠即得 [ZD,ZG]（与是否另有「进入段」无关）；可沿伸至仍与 [ZD,ZG] 相交的后续线段；`entry_seg_idx` 仅指中枢前一线段，供背驰进入段索引，**不参与** ZD/ZG 计算。
- **背驰**（15/24/27 课）：`build_divergences` 以进入/离开段力度对比为主；`divergence_macd_metric` 可选 area/hump/peak/slope/both/either/**either_loose**（多维标量表任一减弱）；`divergence_require_macd_extrema_shrink` 等闸门可选；`bsp1_only_multibi_zs` 可要求中枢最小跨度再出背驰语境。趋势背驰另要求离开段相对进入段**创出更高/更低**价，否则降为盘整类。
- **K 线溯源**：合并后的 `Candle.merged_from` 记录参与的原始 `source_idx`。
- **分型**：`find_fractals` 可对最后一根 K 给出 `confirmed=False` 的进行中分型；确认分型带 `strength_hint`。**笔**仅使用确认分型；可选 `stroke_collapse_shallow_reversal` 折叠浅反向笔；`hydrate_stroke_pause` 标记收盘突破端点（索引与 **标准化 K** 对齐）；`stroke_metrics.hydrate_stroke_metrics` 填充价量斜率/角度/长度/R²/SNR 等力度字段。
- **走势形态**：`lines_form.analyze_lines_form` 对笔序列做粗标签（三笔/盘整/趋势/类趋势等），供区间套扩展。
- **增量**：`CandleNormalizeState` + `normalize_stream_push` 单根喂入合并；`ChanIncrementalAnalyzer` / `rebuild_normalized_from_raw`；`aggregate_candles_to_minutes` 低周期合成高周期；笔内 `fake_bi` 虚拟笔链；中枢 `symmetry_balance` / `symmetry_zs` 启发式。

实盘解读请以课文定义为准；本模块输出用于可重复的规则引擎与 UI 展示。
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Union

from app.core.models import (
    Candle,
    Direction,
    Divergence,
    Fractal,
    Pivot,
    PointType,
    Segment,
    Signal,
    SignalSide,
    Stroke,
    MacdPoint,
)
from app.core.config import settings
from app.services.divergence_metrics import (
    DIVERGENCE_METRIC_ALGOS,
    divergence_pair_weakens,
    movement_metric_scalar,
)
from app.services.indicators import macd_area
from app.services.macd_geometry import (
    dif_dea_cross_zero_in_range,
    macd_abs_peaks_hist_dif_dea,
    macd_histogram_hump_energy,
    movement_hist_peak_max,
    movement_price_slope_per_bar,
    peaks_shrink_vs_reference,
)


Movement = Union[Stroke, Segment]


@dataclass(frozen=True)
class _FeatBar:
    """特征序列元素：用笔画出的价位区间，当作一根 K 做分型。"""

    low: float
    high: float
    stroke_idx: int


def _candle_merged_sources(c: Candle, fallback_raw_idx: int) -> list[int]:
    if c.merged_from:
        return list(c.merged_from)
    sid = c.source_idx if c.source_idx is not None else fallback_raw_idx
    return [sid]


def normalize_candles(candles: list[Candle]) -> list[Candle]:
    """Merge inclusion candles while preserving chronological order."""
    normalized: list[Candle] = []
    direction: Optional[Direction] = None

    for raw_idx, raw_candle in enumerate(candles):
        candle = _ensure_source_indices(raw_candle, raw_idx)
        candle = candle.model_copy(
            update={"merged_from": _candle_merged_sources(candle, raw_idx)}
        )
        if not normalized:
            normalized.append(candle)
            continue

        last = normalized[-1]
        contains = (last.high >= candle.high and last.low <= candle.low) or (
            candle.high >= last.high and candle.low <= last.low
        )
        if not contains:
            if candle.high > last.high and candle.low > last.low:
                direction = Direction.UP
            elif candle.high < last.high and candle.low < last.low:
                direction = Direction.DOWN
            normalized.append(
                candle.model_copy(update={"merged_from": _candle_merged_sources(candle, raw_idx)})
            )
            continue

        if direction == Direction.DOWN:
            high, high_idx = _pick_indexed_extreme(last, candle, "high", prefer_max=False)
            low, low_idx = _pick_indexed_extreme(last, candle, "low", prefer_max=False)
            merged = last.model_copy(
                update={
                    "high": high,
                    "low": low,
                    "open_time": candle.open_time,
                    "time": candle.time,
                    "close": candle.close,
                    "volume": last.volume + candle.volume,
                    "source_idx": candle.source_idx,
                    "high_idx": high_idx,
                    "low_idx": low_idx,
                    "merged_from": _candle_merged_sources(last, raw_idx - 1)
                    + _candle_merged_sources(candle, raw_idx),
                }
            )
        else:
            high, high_idx = _pick_indexed_extreme(last, candle, "high", prefer_max=True)
            low, low_idx = _pick_indexed_extreme(last, candle, "low", prefer_max=True)
            merged = last.model_copy(
                update={
                    "high": high,
                    "low": low,
                    "open_time": candle.open_time,
                    "time": candle.time,
                    "close": candle.close,
                    "volume": last.volume + candle.volume,
                    "source_idx": candle.source_idx,
                    "high_idx": high_idx,
                    "low_idx": low_idx,
                    "merged_from": _candle_merged_sources(last, raw_idx - 1)
                    + _candle_merged_sources(candle, raw_idx),
                }
            )
        normalized[-1] = merged

    return normalized


@dataclass
class CandleNormalizeState:
    """增量包含合并状态，与 `normalize_candles` 逐根扫描语义一致。"""

    normalized: list[Candle] = field(default_factory=list)
    direction: Optional[Direction] = None


def normalize_stream_push(state: CandleNormalizeState, raw_candle: Candle, raw_idx: int) -> None:
    """喂入一根原始 K，就地更新合并序列（用于真·增量 Bar 流）。"""
    candle = _ensure_source_indices(raw_candle, raw_idx)
    candle = candle.model_copy(update={"merged_from": _candle_merged_sources(candle, raw_idx)})
    if not state.normalized:
        state.normalized.append(candle)
        return
    last = state.normalized[-1]
    contains = (last.high >= candle.high and last.low <= candle.low) or (
        candle.high >= last.high and candle.low <= last.low
    )
    if not contains:
        if candle.high > last.high and candle.low > last.low:
            state.direction = Direction.UP
        elif candle.high < last.high and candle.low < last.low:
            state.direction = Direction.DOWN
        state.normalized.append(
            candle.model_copy(update={"merged_from": _candle_merged_sources(candle, raw_idx)})
        )
        return
    if state.direction == Direction.DOWN:
        high, high_idx = _pick_indexed_extreme(last, candle, "high", prefer_max=False)
        low, low_idx = _pick_indexed_extreme(last, candle, "low", prefer_max=False)
        merged = last.model_copy(
            update={
                "high": high,
                "low": low,
                "open_time": candle.open_time,
                "time": candle.time,
                "close": candle.close,
                "volume": last.volume + candle.volume,
                "source_idx": candle.source_idx,
                "high_idx": high_idx,
                "low_idx": low_idx,
                "merged_from": _candle_merged_sources(last, raw_idx - 1)
                + _candle_merged_sources(candle, raw_idx),
            }
        )
    else:
        high, high_idx = _pick_indexed_extreme(last, candle, "high", prefer_max=True)
        low, low_idx = _pick_indexed_extreme(last, candle, "low", prefer_max=True)
        merged = last.model_copy(
            update={
                "high": high,
                "low": low,
                "open_time": candle.open_time,
                "time": candle.time,
                "close": candle.close,
                "volume": last.volume + candle.volume,
                "source_idx": candle.source_idx,
                "high_idx": high_idx,
                "low_idx": low_idx,
                "merged_from": _candle_merged_sources(last, raw_idx - 1)
                + _candle_merged_sources(candle, raw_idx),
            }
        )
    state.normalized[-1] = merged


def _fractal_strength_hint(
    prev_candle: Candle,
    candle: Candle,
    next_candle: Candle,
    *,
    kind: PointType,
) -> float:
    """基于三根 K 线几何与实体的粗评分，用于弱化「力度不足」分型（与笔过滤配套）。"""
    hints: list[float] = []
    rng = max(candle.high - candle.low, 1e-12)
    body = abs(candle.close - candle.open)
    hints.append(min(1.0, body / rng))
    mid_span = max(prev_candle.high, candle.high, next_candle.high) - min(
        prev_candle.low, candle.low, next_candle.low
    )
    hints.append(min(1.0, rng / mid_span) if mid_span > 1e-12 else 0.5)
    if kind == PointType.TOP:
        hints.append(1.0 if candle.close <= max(prev_candle.close, next_candle.close) + 1e-12 else 0.35)
        hi2 = prev_candle.high + (candle.high - prev_candle.high) * 0.5
        hints.append(1.0 if candle.high >= hi2 - 1e-12 else 0.4)
    else:
        hints.append(1.0 if candle.close >= min(prev_candle.close, next_candle.close) - 1e-12 else 0.35)
        lo2 = prev_candle.low - (prev_candle.low - candle.low) * 0.5
        hints.append(1.0 if candle.low <= lo2 + 1e-12 else 0.4)
    return max(0.0, min(1.0, sum(hints) / len(hints)))


def _append_tentative_tail_fractals(candles: list[Candle], fractals: list[Fractal]) -> None:
    """最后一根标准化 K 相对前一根的最简「进行中」极值推断（仅作辅助，不替代三根分型）。"""
    n = len(candles)
    if n < 2:
        return
    last_i = n - 1
    if any(f.norm_idx == last_i and f.confirmed for f in fractals):
        return
    a, b = candles[-2], candles[-1]
    if b.high > a.high and b.low > a.low:
        sid = b.high_idx if b.high_idx is not None else b.source_idx
        if sid is None:
            sid = last_i
        fractals.append(
            Fractal(
                idx=int(sid),
                norm_idx=last_i,
                type=PointType.TOP,
                price=b.high,
                time=b.time,
                confirmed=False,
                strength_hint=None,
            )
        )
        return
    if b.low < a.low and b.high < a.high:
        sid = b.low_idx if b.low_idx is not None else b.source_idx
        if sid is None:
            sid = last_i
        fractals.append(
            Fractal(
                idx=int(sid),
                norm_idx=last_i,
                type=PointType.BOTTOM,
                price=b.low,
                time=b.time,
                confirmed=False,
                strength_hint=None,
            )
        )


def find_fractals(candles: list[Candle], *, include_tentative: Optional[bool] = None) -> list[Fractal]:
    """标准顶/底分型：中间 K 的高、低相对左右均为严格极值（避免「宽 K」误判）。"""
    use_tentative = settings.fractal_include_tentative if include_tentative is None else include_tentative
    fractals: list[Fractal] = []
    for idx in range(1, len(candles) - 1):
        prev_candle = candles[idx - 1]
        candle = candles[idx]
        next_candle = candles[idx + 1]
        if (
            candle.high > prev_candle.high
            and candle.high > next_candle.high
            and candle.low > prev_candle.low
            and candle.low > next_candle.low
        ):
            source_idx = candle.high_idx if candle.high_idx is not None else idx
            strength = _fractal_strength_hint(prev_candle, candle, next_candle, kind=PointType.TOP)
            fractals.append(
                Fractal(
                    idx=source_idx,
                    norm_idx=idx,
                    type=PointType.TOP,
                    price=candle.high,
                    time=candle.time,
                    confirmed=True,
                    strength_hint=strength,
                )
            )
        elif (
            candle.low < prev_candle.low
            and candle.low < next_candle.low
            and candle.high < prev_candle.high
            and candle.high < next_candle.high
        ):
            source_idx = candle.low_idx if candle.low_idx is not None else idx
            strength = _fractal_strength_hint(prev_candle, candle, next_candle, kind=PointType.BOTTOM)
            fractals.append(
                Fractal(
                    idx=source_idx,
                    norm_idx=idx,
                    type=PointType.BOTTOM,
                    price=candle.low,
                    time=candle.time,
                    confirmed=True,
                    strength_hint=strength,
                )
            )
    if use_tentative:
        _append_tentative_tail_fractals(candles, fractals)
    return fractals


STRICT_MIN_STROKE_SPAN = 4  # 5 normalized candles including both fractal candles.


def build_strokes(
    fractals: list[Fractal],
    min_gap: int = STRICT_MIN_STROKE_SPAN,
    candles: Optional[list[Candle]] = None,
) -> list[Stroke]:
    fractals = [f for f in fractals if f.confirmed]
    if not fractals:
        return []

    selected: list[Fractal] = []
    for fractal in sorted(fractals, key=lambda item: item.norm_idx):
        if not selected:
            selected.append(fractal)
            continue

        last = selected[-1]
        if fractal.norm_idx <= last.norm_idx:
            continue

        if fractal.type == last.type:
            if _is_more_extreme(fractal, last):
                selected[-1] = fractal
            continue

        if not _valid_stroke_span(last, fractal, min_gap, candles):
            if _breaks_previous_stroke_start(selected, fractal):
                selected = selected[:-2] + [fractal]
            continue

        selected.append(fractal)

    strokes: list[Stroke] = []
    for start, end in zip(selected, selected[1:]):
        if start.type == end.type:
            continue
        direction = Direction.UP if start.type == PointType.BOTTOM else Direction.DOWN
        strokes.append(
            Stroke(
                # 与 kline_data / MACD / 前端图表一致：使用合并后 K 线在序列中的下标（norm_idx），
                # 勿用 fractal.idx（多为 high_idx/low_idx 的源 bar 号，包含处理后可能与数组下标不一致）。
                start_idx=start.norm_idx,
                end_idx=end.norm_idx,
                norm_start_idx=start.norm_idx,
                norm_end_idx=end.norm_idx,
                start_price=start.price,
                end_price=end.price,
                direction=direction,
            )
        )
    if settings.stroke_collapse_shallow_reversal:
        strokes = _collapse_shallow_center_strokes(strokes, candles, min_gap)
    return strokes


def _collapse_shallow_center_strokes(
    strokes: list[Stroke],
    candles: Optional[list[Candle]],
    min_gap: int,
) -> list[Stroke]:
    """折叠「两侧同向、中间反向且幅度过小」的三笔序列，减轻边缘分型造成的碎笔。"""
    if candles is None or len(strokes) < 3:
        return strokes
    mr = settings.stroke_collapse_middle_max_ratio
    out = list(strokes)
    changed = True
    while changed and len(out) >= 3:
        changed = False
        for i in range(len(out) - 2):
            a, b, c = out[i], out[i + 1], out[i + 2]
            if a.direction != c.direction or b.direction == a.direction:
                continue
            amp_a = abs(a.end_price - a.start_price)
            amp_b = abs(b.end_price - b.start_price)
            amp_c = abs(c.end_price - c.start_price)
            if amp_a < 1e-9 or amp_c < 1e-9:
                continue
            if amp_b / amp_a > mr or amp_b / amp_c > mr:
                continue
            ns = a.norm_start_idx
            ne = c.norm_end_idx
            if ns is None or ne is None:
                continue
            if ne - ns < min_gap:
                continue
            if a.direction == Direction.UP and c.end_price <= a.start_price + 1e-8:
                continue
            if a.direction == Direction.DOWN and c.end_price >= a.start_price - 1e-8:
                continue
            lo = max(0, min(ns, ne))
            hi = min(len(candles) - 1, max(ns, ne))
            segment = candles[lo : hi + 1]
            if segment:
                mx = max(x.high for x in segment)
                mn = min(x.low for x in segment)
                if a.direction == Direction.UP:
                    if abs(a.start_price - mn) > 1e-8 or abs(c.end_price - mx) > 1e-8:
                        continue
                elif abs(a.start_price - mx) > 1e-8 or abs(c.end_price - mn) > 1e-8:
                    continue
            merged = Stroke(
                start_idx=a.start_idx,
                end_idx=c.end_idx,
                norm_start_idx=a.norm_start_idx,
                norm_end_idx=c.norm_end_idx,
                start_price=a.start_price,
                end_price=c.end_price,
                direction=a.direction,
                higher_origin_bar_lo=a.higher_origin_bar_lo,
                higher_origin_bar_hi=c.higher_origin_bar_hi,
                higher_origin_open_time_lo=a.higher_origin_open_time_lo,
                higher_origin_open_time_hi=c.higher_origin_open_time_hi,
            )
            out = out[:i] + [merged] + out[i + 3 :]
            changed = True
            break
    return out


def hydrate_stroke_pause(strokes: list[Stroke], candles: list[Candle]) -> list[Stroke]:
    """笔端点之后若收盘价突破端点价，则标记 pause_after_end（量价停顿的简化定义）。"""
    if not strokes or not candles:
        return strokes
    return [s.model_copy(update={"pause_after_end": _pause_after_stroke(s, candles)}) for s in strokes]


def _pause_after_stroke(stroke: Stroke, candles: list[Candle]) -> bool:
    end_n = stroke.norm_end_idx if stroke.norm_end_idx is not None else stroke.end_idx
    for j in range(end_n + 1, len(candles)):
        c = candles[j]
        if stroke.direction == Direction.UP and c.close > stroke.end_price + 1e-12:
            return True
        if stroke.direction == Direction.DOWN and c.close < stroke.end_price - 1e-12:
            return True
    return False


def build_segments(strokes: list[Stroke]) -> list[Segment]:
    if settings.segment_engine == "strict67":
        return _build_segments_strict67(strokes)
    return _build_segments_legacy(strokes)


def _build_segments_legacy(strokes: list[Stroke]) -> list[Segment]:
    segments: list[Segment] = []
    last_direction: Optional[Direction] = None
    i = 0
    while i <= len(strokes) - 3:
        window = strokes[i : i + 3]
        direction = strokes[i].direction
        if direction == last_direction or not _strokes_have_overlap(window):
            i += 1
            continue

        end_bi = i + 2
        segment = _segment_from_strokes(strokes, i, end_bi)
        while end_bi + 2 < len(strokes):
            extension_window = strokes[end_bi : end_bi + 3]
            extension_stroke = strokes[end_bi + 2]
            if (
                extension_stroke.direction != direction
                or not _strokes_have_overlap(extension_window)
                or not _extends_segment(segment, extension_stroke)
            ):
                break
            end_bi += 2
            segment = _extend_segment(segment, extension_stroke, end_bi)
        segments.append(segment)
        last_direction = segment.direction
        i = segment.end_bi + 1
    return segments


def _feat_bar_from_stroke(stroke: Stroke, stroke_idx: int) -> _FeatBar:
    lo = min(stroke.start_price, stroke.end_price)
    hi = max(stroke.start_price, stroke.end_price)
    return _FeatBar(low=lo, high=hi, stroke_idx=stroke_idx)


def _feat_overlap(a: _FeatBar, b: _FeatBar) -> bool:
    return max(a.low, b.low) < min(a.high, b.high)


def _feat_top_fractal(a: _FeatBar, b: _FeatBar, c: _FeatBar) -> bool:
    return b.high > a.high and b.high > c.high and b.low > a.low and b.low > c.low


def _feat_bottom_fractal(a: _FeatBar, b: _FeatBar, c: _FeatBar) -> bool:
    return b.low < a.low and b.low < c.low and b.high < a.high and b.high < c.high


def _feat_top_actual_break(a: _FeatBar, b: _FeatBar, c: _FeatBar) -> bool:
    """顶分型：第三元素低点须跌破第二元素低点（排除仅靠包含「凑出」的假顶）。"""
    eps = 1e-8
    return c.low < b.low - eps


def _feat_bottom_actual_break(a: _FeatBar, b: _FeatBar, c: _FeatBar) -> bool:
    eps = 1e-8
    return c.high > b.high + eps


def _normalize_feat_bars_include(feats: list[_FeatBar], segment_direction: Direction) -> list[_FeatBar]:
    """67 课标准特征序列：元素间包含按**线段方向**合并（与 K 线包含规则同构）。"""
    if not feats:
        return []
    merged: list[_FeatBar] = []
    for bar in feats:
        if not merged:
            merged.append(bar)
            continue
        last = merged[-1]
        contains = (last.high >= bar.high and last.low <= bar.low) or (
            bar.high >= last.high and bar.low <= last.low
        )
        if not contains:
            merged.append(bar)
            continue
        if segment_direction == Direction.UP:
            new_high = max(last.high, bar.high)
            new_low = max(last.low, bar.low)
        else:
            new_high = min(last.high, bar.high)
            new_low = min(last.low, bar.low)
        merged[-1] = _FeatBar(low=new_low, high=new_high, stroke_idx=bar.stroke_idx)
    return merged


def _resolve_feature_top_segment_end(norm_feats: list[_FeatBar]) -> Optional[_FeatBar]:
    """返回结束向上线段的顶分型**中间元素**（情形一用第一分型；情形二用第二特征序列中的分型）。"""
    for mid in range(1, len(norm_feats) - 1):
        a, b, c = norm_feats[mid - 1], norm_feats[mid], norm_feats[mid + 1]
        if not _feat_top_fractal(a, b, c):
            continue
        if settings.segment_feature_require_actual_break and not _feat_top_actual_break(a, b, c):
            continue
        if _feat_overlap(a, b):
            return b
        sub = norm_feats[mid + 1 :]
        if len(sub) < 3:
            continue
        for mid2 in range(1, len(sub) - 1):
            a2, b2, c2 = sub[mid2 - 1], sub[mid2], sub[mid2 + 1]
            if not _feat_top_fractal(a2, b2, c2):
                continue
            if settings.segment_feature_require_actual_break and not _feat_top_actual_break(a2, b2, c2):
                continue
            return b2
    return None


def _resolve_feature_bottom_segment_end(norm_feats: list[_FeatBar]) -> Optional[_FeatBar]:
    for mid in range(1, len(norm_feats) - 1):
        a, b, c = norm_feats[mid - 1], norm_feats[mid], norm_feats[mid + 1]
        if not _feat_bottom_fractal(a, b, c):
            continue
        if settings.segment_feature_require_actual_break and not _feat_bottom_actual_break(a, b, c):
            continue
        if _feat_overlap(a, b):
            return b
        sub = norm_feats[mid + 1 :]
        if len(sub) < 3:
            continue
        for mid2 in range(1, len(sub) - 1):
            a2, b2, c2 = sub[mid2 - 1], sub[mid2], sub[mid2 + 1]
            if not _feat_bottom_fractal(a2, b2, c2):
                continue
            if settings.segment_feature_require_actual_break and not _feat_bottom_actual_break(a2, b2, c2):
                continue
            return b2
    return None


def _segment_end_bi_after_down_feat_middle(b: _FeatBar, strokes: list[Stroke], pos: int) -> Optional[int]:
    """向上线段：顶分型中间元素为向下笔合并条，线段结束于其后的向上笔。"""
    n = b.stroke_idx + 1
    if n >= len(strokes) or strokes[n].direction != Direction.UP:
        return None
    if n < pos + 2:
        return None
    return n


def _segment_end_bi_after_up_feat_middle(b: _FeatBar, strokes: list[Stroke], pos: int) -> Optional[int]:
    n = b.stroke_idx + 1
    if n >= len(strokes) or strokes[n].direction != Direction.DOWN:
        return None
    if n < pos + 2:
        return None
    return n


def _down_feature_bars(strokes: list[Stroke], pos: int, end_bi: int) -> list[_FeatBar]:
    """向上线段：特征序列为向下笔 X1,X3,...（stroke 下标 pos+1,pos+3,...）。"""
    feats: list[_FeatBar] = []
    j = pos + 1
    while j <= end_bi:
        st = strokes[j]
        if st.direction != Direction.DOWN:
            return []
        feats.append(_feat_bar_from_stroke(st, j))
        j += 2
    return feats


def _up_feature_bars(strokes: list[Stroke], pos: int, end_bi: int) -> list[_FeatBar]:
    """向下线段：特征序列为向上笔 S1,S3,..."""
    feats: list[_FeatBar] = []
    j = pos + 1
    while j <= end_bi:
        st = strokes[j]
        if st.direction != Direction.UP:
            return []
        feats.append(_feat_bar_from_stroke(st, j))
        j += 2
    return feats


def _legacy_extend_segment_from(strokes: list[Stroke], pos: int) -> tuple[int, int]:
    """与旧版一致：从 pos 起三笔重叠后尽量延伸，返回 (end_bi, next_pos)。"""
    direction = strokes[pos].direction
    end_bi = pos + 2
    segment = _segment_from_strokes(strokes, pos, end_bi)
    while end_bi + 2 < len(strokes):
        extension_window = strokes[end_bi : end_bi + 3]
        extension_stroke = strokes[end_bi + 2]
        if (
            extension_stroke.direction != direction
            or not _strokes_have_overlap(extension_window)
            or not _extends_segment(segment, extension_stroke)
        ):
            break
        end_bi += 2
        segment = _extend_segment(segment, extension_stroke, end_bi)
    return end_bi, end_bi + 1


def _scan_feature_end_up(strokes: list[Stroke], pos: int, max_end_bi: int) -> Optional[int]:
    """向上线段：标准特征序列（非包含合并）上顶分型；情形一或情形二（第二特征序列分型）。"""
    for end_bi in range(pos + 6, max_end_bi + 1, 2):
        if end_bi >= len(strokes) or strokes[end_bi].direction != Direction.UP:
            continue
        raw = _down_feature_bars(strokes, pos, end_bi - 1)
        if len(raw) < 3:
            continue
        norm = _normalize_feat_bars_include(raw, Direction.UP)
        if len(norm) < 3:
            continue
        b = _resolve_feature_top_segment_end(norm)
        if b is None:
            continue
        resolved = _segment_end_bi_after_down_feat_middle(b, strokes, pos)
        if resolved is not None:
            return resolved
    return None


def _scan_feature_end_down(strokes: list[Stroke], pos: int, max_end_bi: int) -> Optional[int]:
    for end_bi in range(pos + 6, max_end_bi + 1, 2):
        if end_bi >= len(strokes) or strokes[end_bi].direction != Direction.DOWN:
            continue
        raw = _up_feature_bars(strokes, pos, end_bi - 1)
        if len(raw) < 3:
            continue
        norm = _normalize_feat_bars_include(raw, Direction.DOWN)
        if len(norm) < 3:
            continue
        b = _resolve_feature_bottom_segment_end(norm)
        if b is None:
            continue
        resolved = _segment_end_bi_after_up_feat_middle(b, strokes, pos)
        if resolved is not None:
            return resolved
    return None


def _build_segments_strict67(strokes: list[Stroke]) -> list[Segment]:
    """67 课：标准特征序列（非包含）+ 顶/底分型；情形一或情形二；否则回退 legacy 延伸。"""
    if len(strokes) < 3:
        return []

    segments: list[Segment] = []
    last_seg_dir: Optional[Direction] = None
    pos = 0
    while pos <= len(strokes) - 3:
        window = strokes[pos : pos + 3]
        d0 = strokes[pos].direction
        if not _strokes_have_overlap(window):
            pos += 1
            continue
        if last_seg_dir is not None and d0 == last_seg_dir:
            pos += 1
            continue

        max_end = min(len(strokes) - 1, pos + 160)
        if d0 == Direction.UP:
            end_bi = _scan_feature_end_up(strokes, pos, max_end)
        else:
            end_bi = _scan_feature_end_down(strokes, pos, max_end)

        if end_bi is None or end_bi < pos + 2:
            end_bi, next_pos = _legacy_extend_segment_from(strokes, pos)
        else:
            next_pos = end_bi + 1

        if next_pos <= pos:
            pos += 1
            continue

        segments.append(_segment_from_strokes(strokes, pos, end_bi))
        last_seg_dir = segments[-1].direction
        pos = next_pos
    return segments


def build_pivots(strokes: list[Stroke]) -> list[Pivot]:
    pivots: list[Pivot] = []
    i = 0
    while i <= len(strokes) - 3:
        window = strokes[i : i + 3]
        highs = [max(stroke.start_price, stroke.end_price) for stroke in window]
        lows = [min(stroke.start_price, stroke.end_price) for stroke in window]
        zg = min(highs)
        zd = max(lows)
        if zd < zg:
            pivots.append(
                Pivot(
                    start_bi=i,
                    end_bi=i + 2,
                    start_idx=strokes[i].start_idx,
                    end_idx=strokes[i + 2].end_idx,
                    zg=zg,
                    zd=zd,
                    level="bi",
                    entry_seg_idx=i - 1 if i > 0 else None,
                    leave_seg_idx=i + 3 if i + 3 < len(strokes) else None,
                    direction=strokes[i + 3].direction if i + 3 < len(strokes) else None,
                )
            )
            # Step by 3 strokes per formed pivot to avoid sliding-window duplicates (77 课笔数奇数、中枢窗口重叠).
            i += 3
        else:
            i += 1
    return _finalize_pivot_list(pivots)


def build_segment_pivots(segments: list[Segment]) -> list[Pivot]:
    """线段中枢：任意连续三线段区间有重叠即形成 [ZD,ZG]，再沿伸仍与中区间相交的线段；离开段可缺省。"""
    pivots: list[Pivot] = []
    s = 0
    while s <= len(segments) - 3:
        core = segments[s : s + 3]
        overlap = _range_overlap(core)
        if overlap is None:
            s += 1
            continue

        zd, zg = overlap
        core_end = s + 2
        leaving_idx = s + 3
        while leaving_idx < len(segments) and _segment_overlaps_range(segments[leaving_idx], zd, zg):
            core_end = leaving_idx
            leaving_idx += 1

        span = segments[s : core_end + 1]
        lows = [min(x.start_price, x.end_price) for x in span]
        highs = [max(x.start_price, x.end_price) for x in span]
        zd = max(lows)
        zg = min(highs)
        if zd >= zg:
            s += 1
            continue

        entry_seg_idx = s - 1 if s > 0 else None

        if leaving_idx >= len(segments):
            pivots.append(
                Pivot(
                    start_bi=s,
                    end_bi=core_end,
                    start_idx=segments[s].start_idx,
                    end_idx=segments[core_end].end_idx,
                    zg=zg,
                    zd=zd,
                    level="segment",
                    entry_seg_idx=entry_seg_idx,
                    leave_seg_idx=None,
                    direction=None,
                )
            )
            s += 1
            continue

        leaving = segments[leaving_idx]
        pivots.append(
            Pivot(
                start_bi=s,
                end_bi=core_end,
                start_idx=segments[s].start_idx,
                end_idx=segments[core_end].end_idx,
                zg=zg,
                zd=zd,
                level="segment",
                entry_seg_idx=entry_seg_idx,
                leave_seg_idx=leaving_idx,
                direction=leaving.direction,
            )
        )
        s = leaving_idx + 1
    return _finalize_pivot_list(pivots)


def _finalize_pivot_list(pivots: list[Pivot]) -> list[Pivot]:
    deduped = _dedupe_pivots(pivots)
    if settings.pivot_merge_adjacent_overlaps:
        return _merge_adjacent_overlapping_pivots(deduped)
    return deduped


def _merge_adjacent_overlapping_pivots(pivots: list[Pivot]) -> list[Pivot]:
    """同级、笔序相邻或紧挨、价带相交的中枢合并为一段（[ZD,ZG] 取交集）。"""
    if len(pivots) < 2:
        return pivots
    ordered = sorted(pivots, key=lambda p: (p.start_bi, p.end_bi))
    out: list[Pivot] = [ordered[0]]
    for p in ordered[1:]:
        last = out[-1]
        if last.level != p.level:
            out.append(p)
            continue
        price_ov = min(last.zg, p.zg) > max(last.zd, p.zd)
        bi_close = p.start_bi <= last.end_bi + 1
        if not (price_ov and bi_close):
            out.append(p)
            continue
        zd = max(last.zd, p.zd)
        zg = min(last.zg, p.zg)
        if zd >= zg:
            out.append(p)
            continue
        merged = last.model_copy(
            update={
                "start_bi": min(last.start_bi, p.start_bi),
                "end_bi": max(last.end_bi, p.end_bi),
                "start_idx": min(last.start_idx, p.start_idx),
                "end_idx": max(last.end_idx, p.end_idx),
                "zd": zd,
                "zg": zg,
                "leave_seg_idx": p.leave_seg_idx if p.leave_seg_idx is not None else last.leave_seg_idx,
                "direction": last.direction if last.direction is not None else p.direction,
                "entry_seg_idx": last.entry_seg_idx if last.entry_seg_idx is not None else p.entry_seg_idx,
            }
        )
        out[-1] = merged
    return out


def build_active_stroke(
    candles: list[Candle],
    strokes: list[Stroke],
    min_move_ratio: float = 0.2,
) -> Optional[Stroke]:
    """Build the unconfirmed stroke from normalized candles after the last confirmed endpoint."""
    if not candles or not strokes:
        return None

    last = strokes[-1]
    start_norm_idx = last.norm_end_idx if last.norm_end_idx is not None else _find_norm_idx_by_source(candles, last.end_idx)
    start_norm_idx = min(max(start_norm_idx, 0), len(candles) - 1)
    segment = candles[start_norm_idx:]
    if len(segment) < 2:
        return None

    if last.direction == Direction.DOWN:
        end_offset, end_candle = max(enumerate(segment), key=lambda item: item[1].high)
        end_norm_idx = start_norm_idx + end_offset
        end_price = end_candle.high
        direction = Direction.UP
        if end_norm_idx == start_norm_idx or end_price <= last.end_price:
            return None
    else:
        end_offset, end_candle = min(enumerate(segment), key=lambda item: item[1].low)
        end_norm_idx = start_norm_idx + end_offset
        end_price = end_candle.low
        direction = Direction.DOWN
        if end_norm_idx == start_norm_idx or end_price >= last.end_price:
            return None

    previous_length = abs(last.end_price - last.start_price)
    active_length = abs(end_price - last.end_price)
    if previous_length > 0 and active_length < previous_length * min_move_ratio:
        return None

    start_chart = last.norm_end_idx if last.norm_end_idx is not None else last.end_idx
    return Stroke(
        start_idx=start_chart,
        end_idx=end_norm_idx,
        norm_start_idx=start_chart,
        norm_end_idx=end_norm_idx,
        start_price=last.end_price,
        end_price=end_price,
        direction=direction,
    )


def _pivot_macd_pulls_near_zero_axis(pivot: Pivot, macd_points: list[MacdPoint], abs_eps: float) -> bool:
    """中枢区间内 DIF 是否曾贴近 0 轴或穿越 0 轴（24 课 B 段常见形态，作可选闸门）。"""
    if not macd_points:
        return False
    lo = max(0, min(pivot.start_idx, pivot.end_idx))
    hi = min(len(macd_points) - 1, max(pivot.start_idx, pivot.end_idx))
    if lo > hi:
        return False
    for i in range(lo, hi + 1):
        if abs(macd_points[i].dif) <= abs_eps:
            return True
    prev_sign = 0
    for i in range(lo, hi + 1):
        v = macd_points[i].dif
        if abs(v) <= abs_eps:
            return True
        sign = 1 if v > 0 else -1
        if prev_sign != 0 and sign != 0 and sign != prev_sign:
            return True
        if sign != 0:
            prev_sign = sign
    return False


def _leaving_makes_new_price_extreme_vs_entry(entry: Movement, leaving: Movement) -> bool:
    """24/37 课：离开段相对进入段应创出更高价（向上离开）或更低价（向下离开），否则不构成趋势背驰语境。"""
    eps = 1e-8
    if leaving.direction == Direction.DOWN:
        entry_lo = min(entry.start_price, entry.end_price)
        return leaving.end_price < entry_lo - eps
    if leaving.direction == Direction.UP:
        entry_hi = max(entry.start_price, entry.end_price)
        return leaving.end_price > entry_hi + eps
    return False


def _divergence_structure_kind(pivots: list[Pivot], pivot_idx: int) -> Literal["trend", "zpan_like"]:
    """相邻中枢价域不重叠且整体向上/下堆叠时视为趋势背驰，否则为盘整类。"""
    if pivot_idx <= 0:
        return "zpan_like"
    prev, cur = pivots[pivot_idx - 1], pivots[pivot_idx]
    if prev.zg < cur.zd:
        return "trend"
    if prev.zd > cur.zg:
        return "trend"
    return "zpan_like"


def build_divergences(
    movements: list[Movement],
    pivots: list[Pivot],
    macd_points: list[MacdPoint],
    candles: Optional[list[Candle]] = None,
    max_area_ratio: Optional[float] = None,
    min_breakout_ratio: Optional[float] = None,
) -> list[Divergence]:
    divergences: list[Divergence] = []
    area_ratio_limit = max_area_ratio if max_area_ratio is not None else settings.divergence_ratio
    breakout_ratio = min_breakout_ratio if min_breakout_ratio is not None else settings.divergence_min_breakout_ratio
    for pivot_idx, pivot in enumerate(pivots):
        if (
            settings.bsp1_only_multibi_zs
            and settings.bsp1_min_stroke_span > 0
            and (pivot.end_bi - pivot.start_bi) < settings.bsp1_min_stroke_span
        ):
            continue
        # Entry and leaving are same-direction comparison moves; divergence compares their momentum.
        leaving_idx = pivot.leave_seg_idx if pivot.leave_seg_idx is not None else _first_leaving_segment_index(movements, pivot)
        entry_idx = pivot.entry_seg_idx if pivot.entry_seg_idx is not None else pivot.start_bi - 1
        if entry_idx < 0:
            entry_idx = pivot.start_bi
        if leaving_idx is None or leaving_idx >= len(movements) or entry_idx >= len(movements):
            continue

        leaving = movements[leaving_idx]
        entry = movements[entry_idx]
        if entry.direction != leaving.direction:
            leaving_idx = _first_leaving_segment_index(movements, pivot)
            if leaving_idx is None or leaving_idx >= len(movements):
                continue
            leaving = movements[leaving_idx]
        if entry.direction != leaving.direction or not _leaves_pivot_range(leaving, pivot.zd, pivot.zg):
            continue

        entry_area = movement_macd_area(macd_points, entry)
        leave_area = movement_macd_area(macd_points, leaving)
        entry_hump = macd_histogram_hump_energy(macd_points, entry.start_idx, entry.end_idx)
        leave_hump = macd_histogram_hump_energy(macd_points, leaving.start_idx, leaving.end_idx)
        entry_peak = movement_hist_peak_max(macd_points, entry.start_idx, entry.end_idx)
        leave_peak = movement_hist_peak_max(macd_points, leaving.start_idx, leaving.end_idx)
        entry_slope = movement_price_slope_per_bar(
            entry.start_idx, entry.end_idx, entry.start_price, entry.end_price
        )
        leave_slope = movement_price_slope_per_bar(
            leaving.start_idx, leaving.end_idx, leaving.start_price, leaving.end_price
        )

        ratio_a = leave_area / entry_area if entry_area > 1e-18 else 0.0
        ratio_h = leave_hump / entry_hump if entry_hump > 1e-18 else 0.0
        ratio_p = leave_peak / entry_peak if entry_peak > 1e-18 else 0.0
        ratio_s = leave_slope / entry_slope if entry_slope > 1e-18 else 0.0

        metric = settings.divergence_macd_metric
        area_ok = entry_area > 1e-18 and (leave_area / entry_area) < area_ratio_limit
        hump_ok = entry_hump > 1e-18 and (leave_hump / entry_hump) < area_ratio_limit
        peak_ok = entry_peak > 1e-18 and (leave_peak / entry_peak) < area_ratio_limit
        slope_ok = entry_slope > 1e-18 and (leave_slope / entry_slope) < area_ratio_limit

        ratio_out_el = ratio_a
        if metric == "area":
            metric_ok = area_ok
        elif metric == "hump":
            metric_ok = hump_ok
        elif metric == "peak":
            metric_ok = peak_ok
        elif metric == "slope":
            metric_ok = slope_ok
        elif metric == "either":
            metric_ok = area_ok or hump_ok
        elif metric == "either_loose":
            candle_ctx = candles if candles is not None else []
            metric_ok = False
            for algo in DIVERGENCE_METRIC_ALGOS:
                if divergence_pair_weakens(algo, macd_points, candle_ctx, entry, leaving, area_ratio_limit):
                    metric_ok = True
                    ev_a = movement_metric_scalar(algo, macd_points, candle_ctx, entry)
                    lv_a = movement_metric_scalar(algo, macd_points, candle_ctx, leaving)
                    ratio_out_el = lv_a / ev_a if ev_a > 1e-18 else ratio_a
                    break
        else:
            metric_ok = area_ok and hump_ok
        if not metric_ok:
            continue

        if not _has_sufficient_breakout(entry, leaving, pivot, breakout_ratio):
            continue

        if settings.divergence_require_pivot_macd_zero_axis and not _pivot_macd_pulls_near_zero_axis(
            pivot, macd_points, settings.divergence_macd_zero_axis_abs
        ):
            continue

        if settings.divergence_require_leave_segment_zero_cross and not dif_dea_cross_zero_in_range(
            macd_points,
            leaving.start_idx,
            leaving.end_idx,
            abs_eps=settings.divergence_macd_zero_axis_abs,
        ):
            continue

        if settings.divergence_require_macd_extrema_shrink and not _macd_extrema_shrinks_vs_entry(
            macd_points, entry, leaving
        ):
            continue

        sk = _divergence_structure_kind(pivots, pivot_idx)
        if sk == "trend" and not _leaving_makes_new_price_extreme_vs_entry(entry, leaving):
            sk = "zpan_like"
        sk_label = "趋势背驰" if sk == "trend" else "盘整类背驰"
        detail_bits: list[str] = []
        if entry_area > 1e-18:
            detail_bits.append(f"柱面积比={ratio_a:.2f}")
        if entry_hump > 1e-18:
            detail_bits.append(f"驼峰能量比={ratio_h:.2f}")
        if entry_peak > 1e-18:
            detail_bits.append(f"柱峰比={ratio_p:.2f}")
        if entry_slope > 1e-18:
            detail_bits.append(f"价斜率比={ratio_s:.2f}")
        detail = "，".join(detail_bits) if detail_bits else "力度对比"
        if metric == "peak":
            ratio_out = ratio_p
        elif metric == "slope":
            ratio_out = ratio_s
        elif metric == "hump":
            ratio_out = ratio_h
        elif metric == "either_loose":
            ratio_out = ratio_out_el
        else:
            ratio_out = ratio_a if entry_area > 1e-18 else ratio_h
        divergences.append(
            Divergence(
                level=pivot.level,
                direction=leaving.direction,
                pivot_idx=pivot_idx,
                entry_seg_idx=entry_idx,
                leave_seg_idx=leaving_idx,
                idx=leaving.end_idx,
                price=leaving.end_price,
                entry_area=entry_area,
                leave_area=leave_area,
                ratio=ratio_out,
                description=f"{sk_label}，离开段 MACD {detail}",
                structure_kind=sk,
            )
        )
    return divergences


def build_t1p_pan_signals(
    candles: list[Candle],
    strokes: list[Stroke],
    macd_points: list[MacdPoint],
) -> tuple[list[Signal], list[Signal]]:
    """无笔中枢时：最近「同向—反向—同向」三笔，后同向段不创新低/高且 MACD 柱面积相对减弱 → 盘整一类候选。"""
    if not settings.enable_t1p_pan_first_signals or len(strokes) < 3 or not macd_points:
        return [], []
    buys: list[Signal] = []
    sells: list[Signal] = []
    ratio_limit = settings.divergence_ratio
    eps = 1e-8
    j: Optional[int] = None
    for k in range(len(strokes) - 3, -1, -1):
        a, b, c = strokes[k], strokes[k + 1], strokes[k + 2]
        if a.direction == c.direction and b.direction != a.direction:
            j = k
            break
    if j is None:
        return [], []
    a, _, c = strokes[j], strokes[j + 1], strokes[j + 2]
    if a.direction == Direction.DOWN:
        la = min(a.start_price, a.end_price)
        lc = min(c.start_price, c.end_price)
        if lc + eps < la:
            return [], []
        ea = movement_macd_area(macd_points, a)
        ec = movement_macd_area(macd_points, c)
        if ea <= 1e-18 or ec / ea >= ratio_limit:
            return [], []
        strength = _safe_strength(ea, ec)
        buys.append(
            _signal(
                candles,
                SignalSide.BUY,
                "first",
                c.end_idx,
                c.end_price,
                "盘整一类买点候选(T1P)：尚无比中枢，后一段下跌未破前段低且 MACD 柱面积相对减弱",
                strength,
                pivot_level=None,
                pivot_idx=None,
                entry_seg_idx=j,
                leave_seg_idx=j + 2,
                macd_ratio=ec / ea,
                evidence=f"T1P 无中枢｜笔#{j}→#{j + 2}｜MACD面积比={ec/ea:.2f}",
            )
        )
        return buys, []
    if a.direction == Direction.UP:
        ha = max(a.start_price, a.end_price)
        hc = max(c.start_price, c.end_price)
        if hc > ha + eps:
            return [], []
        ea = movement_macd_area(macd_points, a)
        ec = movement_macd_area(macd_points, c)
        if ea <= 1e-18 or ec / ea >= ratio_limit:
            return [], []
        strength = _safe_strength(ea, ec)
        sells.append(
            _signal(
                candles,
                SignalSide.SELL,
                "first",
                c.end_idx,
                c.end_price,
                "盘整一类卖点候选(T1P)：尚无比中枢，后一段上涨未过前段高且 MACD 柱面积相对减弱",
                strength,
                pivot_level=None,
                pivot_idx=None,
                entry_seg_idx=j,
                leave_seg_idx=j + 2,
                macd_ratio=ec / ea,
                evidence=f"T1P 无中枢｜笔#{j}→#{j + 2}｜MACD面积比={ec/ea:.2f}",
            )
        )
        return [], sells
    return [], []


def build_signals(
    candles: list[Candle],
    movements: list[Movement],
    pivots: list[Pivot],
    divergences: list[Divergence],
    trim_latest: Optional[int] = 12,
    level: str = "bi",
) -> tuple[list[Signal], list[Signal]]:
    buy_signals: list[Signal] = []
    sell_signals: list[Signal] = []

    first_signal_segments: list[tuple[Signal, int, Pivot, int]] = []
    for divergence in divergences:
        if divergence.pivot_idx >= len(pivots):
            continue
        pivot = pivots[divergence.pivot_idx]
        strength = _safe_strength(divergence.entry_area, divergence.leave_area)
        level_label = "笔中枢" if divergence.level == "bi" else "线段中枢"
        sk = "趋势" if divergence.structure_kind == "trend" else "盘整类"
        evidence = (
            f"{level_label}#{divergence.pivot_idx}，{sk}背驰，进入#{divergence.entry_seg_idx}，"
            f"离开#{divergence.leave_seg_idx}，MACD面积比={divergence.ratio:.2f}"
        )

        if divergence.direction == Direction.DOWN:
            buy_title = (
                "一买候选（趋势背驰语境）"
                if divergence.structure_kind == "trend"
                else "盘整背驰类买点候选"
            )
            signal = _signal(
                candles=candles,
                side=SignalSide.BUY,
                kind="first",
                idx=divergence.idx,
                price=divergence.price,
                description=f"{buy_title}：向下离开中枢后，{divergence.description}，出现底背驰",
                strength=strength,
                pivot_level=divergence.level,
                pivot_idx=divergence.pivot_idx,
                entry_seg_idx=divergence.entry_seg_idx,
                leave_seg_idx=divergence.leave_seg_idx,
                macd_ratio=divergence.ratio,
                evidence=evidence,
                level=level,
                stop_loss=_sl_buy(pivot.zd, pivot.zg),
                take_profit=divergence.price + 2 * (divergence.price - _sl_buy(pivot.zd, pivot.zg)) if divergence.price > pivot.zd else None,
                take_profit_1=divergence.price + (divergence.price - _sl_buy(pivot.zd, pivot.zg)) if divergence.price > pivot.zd else None,
            )
            buy_signals.append(signal)
            first_signal_segments.append((signal, divergence.leave_seg_idx, pivot, divergence.pivot_idx))
        elif divergence.direction == Direction.UP:
            sell_title = (
                "一卖候选（趋势背驰语境）"
                if divergence.structure_kind == "trend"
                else "盘整背驰类卖点候选"
            )
            signal = _signal(
                candles=candles,
                side=SignalSide.SELL,
                kind="first",
                idx=divergence.idx,
                price=divergence.price,
                description=f"{sell_title}：向上离开中枢后，{divergence.description}，出现顶背驰",
                strength=strength,
                pivot_level=divergence.level,
                pivot_idx=divergence.pivot_idx,
                entry_seg_idx=divergence.entry_seg_idx,
                leave_seg_idx=divergence.leave_seg_idx,
                macd_ratio=divergence.ratio,
                evidence=evidence,
                level=level,
                stop_loss=_sl_sell(pivot.zd, pivot.zg),
                take_profit=divergence.price - 2 * (_sl_sell(pivot.zd, pivot.zg) - divergence.price) if pivot.zg > divergence.price else None,
                take_profit_1=divergence.price - (_sl_sell(pivot.zd, pivot.zg) - divergence.price) if pivot.zg > divergence.price else None,
            )
            sell_signals.append(signal)
            first_signal_segments.append((signal, divergence.leave_seg_idx, pivot, divergence.pivot_idx))

    for first_signal, segment_idx, pivot, pivot_idx in first_signal_segments:
        second = _second_signal(candles, movements, first_signal, segment_idx, level=level)
        if second is not None:
            (buy_signals if second.side == SignalSide.BUY else sell_signals).append(second)
            t2s = _second_extend_signal(
                candles, movements, first_signal, segment_idx, second, pivot_idx, pivots, level=level
            )
            if t2s is not None:
                (buy_signals if t2s.side == SignalSide.BUY else sell_signals).append(t2s)
        third = _third_signal(candles, movements, first_signal, segment_idx, pivot, level=level)
        if third is not None:
            (buy_signals if third.side == SignalSide.BUY else sell_signals).append(third)

    cl_buy, cl_sell = _class_like_second_signals(candles, movements, pivots, level=level)
    buy_signals.extend(cl_buy)
    sell_signals.extend(cl_sell)

    for pivot_idx, pivot in enumerate(pivots):
        for sig in _standalone_third_signals_for_pivot(candles, movements, pivot, pivot_idx, sig_level=level):
            (buy_signals if sig.side == SignalSide.BUY else sell_signals).append(sig)

    if settings.enable_standalone_second_signals:
        for pivot_idx, pivot in enumerate(pivots):
            for sig in _standalone_second_signals_for_pivot(candles, movements, pivot, pivot_idx, sig_level=level):
                (buy_signals if sig.side == SignalSide.BUY else sell_signals).append(sig)

    buy_out = _latest_signal_per_pivot_side(buy_signals)
    sell_out = _latest_signal_per_pivot_side(sell_signals)
    if trim_latest is not None:
        buy_out = buy_out[-trim_latest:]
        sell_out = sell_out[-trim_latest:]
    return buy_out, sell_out


def segment_macd_area(points: list[MacdPoint], segment: Segment) -> float:
    return movement_macd_area(points, segment)


def _latest_signal_per_pivot_side(signals: list[Signal]) -> list[Signal]:
    latest: dict[tuple[Optional[str], Optional[int], SignalSide, str], Signal] = {}
    passthrough: list[Signal] = []
    for signal in signals:
        if signal.pivot_idx is None:
            passthrough.append(signal)
            continue
        key = (signal.pivot_level, signal.pivot_idx, signal.side, signal.kind)
        current = latest.get(key)
        if current is None or signal.idx >= current.idx:
            latest[key] = signal
    return sorted(passthrough + list(latest.values()), key=lambda signal: signal.idx)


def movement_macd_area(points: list[MacdPoint], movement: Movement) -> float:
    return macd_area(points, movement.start_idx, movement.end_idx)


def _macd_extrema_shrinks_vs_entry(macd_points: list[MacdPoint], entry: Movement, leaving: Movement) -> bool:
    ref = macd_abs_peaks_hist_dif_dea(macd_points, entry.start_idx, entry.end_idx)
    return peaks_shrink_vs_reference(
        macd_points,
        ref,
        (leaving.start_idx, leaving.end_idx),
        max_ratio=settings.divergence_macd_extrema_max_ratio,
        require_dea=settings.divergence_macd_extrema_require_dea,
    )


def _next_pivot_start_bi(pivots: list[Pivot], pivot_idx: int, cur: Pivot) -> Optional[int]:
    for j in range(pivot_idx + 1, len(pivots)):
        if pivots[j].start_bi > cur.end_bi:
            return pivots[j].start_bi
    return None


def _class_like_second_signals(
    candles: list[Candle],
    movements: list[Stroke],
    pivots: list[Pivot],
    level: str = "bi",
) -> tuple[list[Signal], list[Signal]]:
    """类二买/类二卖：中枢震荡内或中枢下方抬高低点 / 压低高点（不依赖一类背驰）。

    v2: 放宽 lo_a / hi_a 范围，允许第一个低点/高点在中枢外（破中枢后反转形成类二买/卖）。
    """
    buys: list[Signal] = []
    sells: list[Signal] = []
    eps = 1e-8
    for pivot_idx, pivot in enumerate(pivots):
        if pivot.level != "bi":
            continue
        nxt = _next_pivot_start_bi(pivots, pivot_idx, pivot)
        hi = nxt if nxt is not None else len(movements)
        # 从中枢内部最后几笔开始扫描（包含中枢构成笔内的形态）
        scan_start = max(pivot.start_bi, pivot.end_bi - 4)
        if scan_start + 3 > hi:
            continue
        post = movements[scan_start : hi]
        base = scan_start
        pivot_h = max(pivot.zg - pivot.zd, eps)
        for i in range(len(post) - 2):
            a, b, c = post[i], post[i + 1], post[i + 2]
            if a.direction == Direction.DOWN and b.direction == Direction.UP and c.direction == Direction.DOWN:
                lo_a = min(a.start_price, a.end_price)
                lo_c = min(c.start_price, c.end_price)
                # 允许 lo_a 在中枢内或中枢下方（最多 2% 距离，避免过远噪声）
                max_drop = max(2 * pivot_h, 0.02 * pivot.zd)
                if lo_a >= pivot.zg - eps or lo_a < pivot.zd - max_drop:
                    continue
                if lo_c <= lo_a + eps:
                    continue
                if lo_c <= pivot.zd + eps and lo_a >= pivot.zd + eps:
                    continue
                inside = pivot.zd + eps < lo_a < pivot.zg - eps
                desc = ("类二买：中枢震荡内后段低点高于前段低点" if inside
                        else "类二买(中枢外)：破中枢后反转，后段低点高于前段低点")
                sl = lo_a - _STOP_LOSS_BUFFER_RATIO * pivot_h
                buys.append(
                    _signal(
                        candles,
                        SignalSide.BUY,
                        "second_class",
                        c.end_idx,
                        c.end_price,
                        desc,
                        0.62 if inside else 0.58,
                        pivot_level="bi",
                        pivot_idx=pivot_idx,
                        entry_seg_idx=base + i,
                        leave_seg_idx=base + i + 2,
                        macd_ratio=None,
                        evidence=f"笔中枢#{pivot_idx}，段#{base + i}..#{base + i + 2}",
                        level=level,
                        stop_loss=sl,
                        take_profit=c.end_price + 2 * (c.end_price - sl),
                        take_profit_1=c.end_price + (c.end_price - sl),
                    )
                )
                break
        for i in range(len(post) - 2):
            a, b, c = post[i], post[i + 1], post[i + 2]
            if a.direction == Direction.UP and b.direction == Direction.DOWN and c.direction == Direction.UP:
                hi_a = max(a.start_price, a.end_price)
                hi_c = max(c.start_price, c.end_price)
                # 允许 hi_a 在中枢内或中枢上方（最多 2% 距离）
                max_rise = max(2 * pivot_h, 0.02 * pivot.zg)
                if hi_a <= pivot.zd + eps or hi_a > pivot.zg + max_rise:
                    continue
                if hi_c >= hi_a - eps:
                    continue
                if hi_c >= pivot.zg - eps and hi_a <= pivot.zg - eps:
                    continue
                inside = pivot.zd + eps < hi_a < pivot.zg - eps
                desc = ("类二卖：中枢震荡内后段高点低于前段高点" if inside
                        else "类二卖(中枢外)：破中枢后反转，后段高点低于前段高点")
                sl = hi_a + _STOP_LOSS_BUFFER_RATIO * pivot_h
                sells.append(
                    _signal(
                        candles,
                        SignalSide.SELL,
                        "second_class",
                        c.end_idx,
                        c.end_price,
                        desc,
                        0.62 if inside else 0.58,
                        pivot_level="bi",
                        pivot_idx=pivot_idx,
                        entry_seg_idx=base + i,
                        leave_seg_idx=base + i + 2,
                        macd_ratio=None,
                        evidence=f"笔中枢#{pivot_idx}，段#{base + i}..#{base + i + 2}",
                        level=level,
                        stop_loss=sl,
                        take_profit=c.end_price - 2 * (sl - c.end_price),
                        take_profit_1=c.end_price - (sl - c.end_price),
                    )
                )
                break
    return buys, sells


def _segment_from_strokes(strokes: list[Stroke], start_bi: int, end_bi: int) -> Segment:
    start = strokes[start_bi]
    end = strokes[end_bi]
    direction = start.direction
    return Segment(
        start_bi=start_bi,
        end_bi=end_bi,
        start_idx=start.start_idx,
        end_idx=end.end_idx,
        start_price=start.start_price,
        end_price=end.end_price,
        direction=direction,
        confirmed=True,
    )


def _extends_segment(segment: Segment, stroke: Stroke) -> bool:
    if segment.direction == Direction.UP:
        return stroke.end_price > segment.end_price
    return stroke.end_price < segment.end_price


def _strokes_have_overlap(strokes: list[Stroke]) -> bool:
    if len(strokes) < 3:
        return False
    lows = [min(stroke.start_price, stroke.end_price) for stroke in strokes]
    highs = [max(stroke.start_price, stroke.end_price) for stroke in strokes]
    return max(lows) < min(highs)


def _extend_segment(segment: Segment, stroke: Stroke, stroke_idx: int) -> Segment:
    return segment.model_copy(
        update={
            "end_bi": stroke_idx,
            "end_idx": stroke.end_idx,
            "end_price": stroke.end_price,
        }
    )


def _range_overlap(items: list[Movement]) -> Optional[tuple[float, float]]:
    if not items:
        return None
    lows = [min(item.start_price, item.end_price) for item in items]
    highs = [max(item.start_price, item.end_price) for item in items]
    zd = max(lows)
    zg = min(highs)
    if zd < zg:
        return zd, zg
    return None


def _dedupe_pivots(pivots: list[Pivot]) -> list[Pivot]:
    deduped: list[Pivot] = []
    for pivot in pivots:
        duplicate_idx = next(
            (idx for idx, existing in enumerate(deduped) if _is_duplicate_pivot(existing, pivot)),
            None,
        )
        if duplicate_idx is None:
            deduped.append(pivot)
            continue
        deduped[duplicate_idx] = _merge_pivots(deduped[duplicate_idx], pivot)
    return deduped


def _is_duplicate_pivot(left: Pivot, right: Pivot) -> bool:
    if left.level != right.level:
        return False
    if not _pivot_time_windows_overlap(left, right):
        return False
    left_width = max(left.zg - left.zd, 1e-8)
    right_width = max(right.zg - right.zd, 1e-8)
    overlap = min(left.zg, right.zg) - max(left.zd, right.zd)
    return overlap > 0 and overlap / min(left_width, right_width) >= settings.pivot_dedupe_overlap_ratio


def _pivot_time_windows_overlap(left: Pivot, right: Pivot) -> bool:
    return max(left.start_idx, right.start_idx) <= min(left.end_idx, right.end_idx)


def _merge_pivots(left: Pivot, right: Pivot) -> Pivot:
    # Keep the first formation window for rendering. Extending the visual box across
    # every duplicate discovery turns one pivot into a long background band.
    entry_seg_idx = left.entry_seg_idx if left.entry_seg_idx is not None else right.entry_seg_idx
    took_entry_from_right = left.entry_seg_idx is None and right.entry_seg_idx is not None
    return left.model_copy(
        update={
            "start_bi": left.start_bi,
            "end_bi": left.end_bi,
            "start_idx": left.start_idx,
            "end_idx": left.end_idx,
            "entry_seg_idx": entry_seg_idx,
            # If we had to take the entry from the right pivot (e.g. start_bi=0 pivot),
            # prefer the matching leaving context from the same pivot for divergence/signals.
            "leave_seg_idx": (
                right.leave_seg_idx
                if took_entry_from_right and right.leave_seg_idx is not None
                else (left.leave_seg_idx if left.leave_seg_idx is not None else right.leave_seg_idx)
            ),
            "direction": (
                right.direction
                if took_entry_from_right and right.direction is not None
                else (left.direction if left.direction is not None else right.direction)
            ),
        }
    )


def _segment_overlaps_range(segment: Movement, zd: float, zg: float) -> bool:
    low = min(segment.start_price, segment.end_price)
    high = max(segment.start_price, segment.end_price)
    return max(low, zd) < min(high, zg)


def _leaves_pivot_range(segment: Movement, zd: float, zg: float) -> bool:
    if segment.direction == Direction.UP:
        return segment.end_price > zg
    return segment.end_price < zd


# 离开幅度相对中枢高度偏小 → 标为「类三」；否则仍为标准「三」类独立几何分支。
_THIRD_CLASS_SHALLOW_LEAVE_RATIO = 0.10
# Stop-loss buffer: push stop this fraction of pivot height beyond ZD/ZG for more room.
_STOP_LOSS_BUFFER_RATIO = 0.15


def _sl_buy(pivot_zd: float, pivot_zg: float) -> float:
    """Stop-loss for a BUY signal: below ZD with buffer."""
    h = pivot_zg - pivot_zd
    return pivot_zd - _STOP_LOSS_BUFFER_RATIO * h


def _sl_sell(pivot_zd: float, pivot_zg: float) -> float:
    """Stop-loss for a SELL signal: above ZG with buffer."""
    h = pivot_zg - pivot_zd
    return pivot_zg + _STOP_LOSS_BUFFER_RATIO * h


def _sl_buy_third(pivot_zd: float, pivot_zg: float) -> float:
    """Stop-loss for a THIRD-class BUY: below ZG (price shouldn't fall back into pivot)."""
    h = pivot_zg - pivot_zd
    return pivot_zg - _STOP_LOSS_BUFFER_RATIO * h


def _sl_sell_third(pivot_zd: float, pivot_zg: float) -> float:
    """Stop-loss for a THIRD-class SELL: above ZD (price shouldn't rise back into pivot)."""
    h = pivot_zg - pivot_zd
    return pivot_zd + _STOP_LOSS_BUFFER_RATIO * h


def _shallow_leave_up(leave: Movement, zd: float, zg: float) -> bool:
    if not _leaves_pivot_range(leave, zd, zg) or leave.direction != Direction.UP:
        return False
    h = max(zg - zd, 1e-9)
    return (leave.end_price - zg) <= _THIRD_CLASS_SHALLOW_LEAVE_RATIO * h


def _shallow_leave_down(leave: Movement, zd: float, zg: float) -> bool:
    if not _leaves_pivot_range(leave, zd, zg) or leave.direction != Direction.DOWN:
        return False
    h = max(zg - zd, 1e-9)
    return (zd - leave.end_price) <= _THIRD_CLASS_SHALLOW_LEAVE_RATIO * h


def _has_sufficient_breakout(entry: Movement, leaving: Movement, pivot: Pivot, min_ratio: float) -> bool:
    pivot_height = max(pivot.zg - pivot.zd, 1e-8)
    required = pivot_height * min_ratio
    if leaving.direction == Direction.UP:
        return leaving.end_price > entry.end_price and leaving.end_price - max(entry.end_price, pivot.zg) >= required
    return leaving.end_price < entry.end_price and min(entry.end_price, pivot.zd) - leaving.end_price >= required


def _range_proxy(zd: float, zg: float) -> Segment:
    return Segment(
        start_bi=0,
        end_bi=0,
        start_idx=0,
        end_idx=0,
        start_price=zd,
        end_price=zg,
        direction=Direction.UP,
    )


def _first_leaving_segment_index(segments: list[Movement], pivot: Pivot) -> Optional[int]:
    for idx in range(pivot.end_bi + 1, len(segments)):
        segment = segments[idx]
        if segment.direction == Direction.UP and segment.end_price > pivot.zg:
            return idx
        if segment.direction == Direction.DOWN and segment.end_price < pivot.zd:
            return idx
    return None


def _standalone_third_signals_for_pivot(
    candles: list[Candle],
    movements: list[Movement],
    pivot: Pivot,
    pivot_idx: int,
    sig_level: str = "bi",
) -> list[Signal]:
    """20 课：三买/三卖为离开+回抽确认，不必以一类背驰为前提。"""
    out: list[Signal] = []
    zd, zg = pivot.zd, pivot.zg
    pivot_lv = pivot.level
    n = len(movements)
    k = pivot.end_bi + 1
    while k <= n - 3:
        up_leave = movements[k]
        if up_leave.direction != Direction.UP or not _leaves_pivot_range(up_leave, zd, zg):
            k += 1
            continue
        retrace = movements[k + 1]
        confirm = movements[k + 2]
        if retrace.direction != Direction.DOWN or confirm.direction != Direction.UP:
            k += 1
            continue
        if min(retrace.start_price, retrace.end_price) <= zg:
            k += 1
            continue
        shallow = _shallow_leave_up(up_leave, zd, zg)
        out.append(
            _signal(
                candles=candles,
                side=SignalSide.BUY,
                kind="third_class" if shallow else "third",
                idx=retrace.end_idx,
                price=retrace.end_price,
                description=(
                    "类三买：向上浅离开中枢后回抽不破 ZG，再次上行确认（离开幅度相对中枢高度偏小）。"
                    if shallow
                    else "三买：向上离开中枢后回抽不破 ZG，再次上行确认（可无本级别一类背驰）"
                ),
                strength=0.66 if shallow else 0.78,
                pivot_level=pivot_lv,
                pivot_idx=pivot_idx,
                entry_seg_idx=k,
                leave_seg_idx=k + 2,
                macd_ratio=None,
                evidence=f"{'笔' if pivot_lv == 'bi' else '线段'}中枢#{pivot_idx}，离开#{k}回抽#{k + 1}确认#{k + 2}",
                level=sig_level,
                stop_loss=_sl_buy_third(zd, zg),
                take_profit=retrace.end_price + 2 * (retrace.end_price - _sl_buy_third(zd, zg)),
                take_profit_1=retrace.end_price + (retrace.end_price - _sl_buy_third(zd, zg)),
            )
        )
        k += 3

    k = pivot.end_bi + 1
    while k <= n - 3:
        dn_leave = movements[k]
        if dn_leave.direction != Direction.DOWN or not _leaves_pivot_range(dn_leave, zd, zg):
            k += 1
            continue
        retrace = movements[k + 1]
        confirm = movements[k + 2]
        if retrace.direction != Direction.UP or confirm.direction != Direction.DOWN:
            k += 1
            continue
        if max(retrace.start_price, retrace.end_price) >= zd:
            k += 1
            continue
        shallow = _shallow_leave_down(dn_leave, zd, zg)
        out.append(
            _signal(
                candles=candles,
                side=SignalSide.SELL,
                kind="third_class" if shallow else "third",
                idx=retrace.end_idx,
                price=retrace.end_price,
                description=(
                    "类三卖：向下浅离开中枢后反抽不回 ZD，再次下行确认（离开幅度相对中枢高度偏小）。"
                    if shallow
                    else "三卖：向下离开中枢后反抽不回 ZD，再次下行确认（可无本级别一类背驰）"
                ),
                strength=0.66 if shallow else 0.78,
                pivot_level=pivot_lv,
                pivot_idx=pivot_idx,
                entry_seg_idx=k,
                leave_seg_idx=k + 2,
                macd_ratio=None,
                evidence=f"{'笔' if pivot_lv == 'bi' else '线段'}中枢#{pivot_idx}，离开#{k}反抽#{k + 1}确认#{k + 2}",
                level=sig_level,
                stop_loss=_sl_sell_third(zd, zg),
                take_profit=retrace.end_price - 2 * (_sl_sell_third(zd, zg) - retrace.end_price),
                take_profit_1=retrace.end_price - (_sl_sell_third(zd, zg) - retrace.end_price),
            )
        )
        k += 3

    return out


def _standalone_second_signals_for_pivot(
    candles: list[Candle],
    movements: list[Movement],
    pivot: Pivot,
    pivot_idx: int,
    sig_level: str = "bi",
    _MAX_SCAN_STROKES: int = 12,
) -> list[Signal]:
    """独立形态二买/二卖：不依赖一类背驰，纯看 DOWN-UP-DOWN 抬高低点 / UP-DOWN-UP 压低高点。

    扫描范围：pivot.end_bi + 1 开始最多 _MAX_SCAN_STROKES 笔。
    与 _class_like_second_signals 互补：后者覆盖中枢内部，本函数覆盖中枢外。
    """
    out: list[Signal] = []
    zd, zg = pivot.zd, pivot.zg
    pivot_lv = pivot.level
    pivot_h = max(zg - zd, 1e-9)
    end_k = min(pivot.end_bi + 1 + _MAX_SCAN_STROKES, len(movements))
    k = pivot.end_bi + 1

    # BUY: DOWN(a) → UP(b) → DOWN(c), lo_c > lo_a
    while k + 2 < end_k:
        a = movements[k]
        if a.direction != Direction.DOWN:
            k += 1
            continue
        b = movements[k + 1]
        if b.direction != Direction.UP:
            k += 1
            continue
        c = movements[k + 2]
        if c.direction != Direction.DOWN:
            k += 1
            continue
        lo_a = min(a.start_price, a.end_price)
        lo_c = min(c.start_price, c.end_price)
        if lo_c <= lo_a:
            k += 1
            continue
        # 至少需要 0.1% 的抬升幅度，避免噪声
        if (lo_c - lo_a) / max(lo_a, 1e-9) < 0.001:
            k += 1
            continue
        # 不接受已经由 _class_like_second_signals 处理的中枢内信号
        if pivot.zd < lo_a < pivot.zg:
            k += 1
            continue
        sl = lo_a - _STOP_LOSS_BUFFER_RATIO * pivot_h
        out.append(
            _signal(
                candles=candles,
                side=SignalSide.BUY,
                kind="second_class",
                idx=c.end_idx,
                price=c.end_price,
                description="形态二买：后段低点高于前段低点（独立检测，无需背驰）",
                strength=0.55,
                pivot_level=pivot_lv,
                pivot_idx=pivot_idx,
                entry_seg_idx=k,
                leave_seg_idx=k + 2,
                macd_ratio=None,
                evidence=f"{'笔' if pivot_lv == 'bi' else '线段'}中枢#{pivot_idx}，形态二买 #{k}..#{k + 2}，抬升{((lo_c - lo_a) / lo_a * 100):.2f}%",
                level=sig_level,
                stop_loss=sl,
                take_profit=c.end_price + 2 * (c.end_price - sl),
                take_profit_1=c.end_price + (c.end_price - sl),
            )
        )
        break  # 只取第一个匹配

    # SELL: UP(a) → DOWN(b) → UP(c), hi_c < hi_a
    k = pivot.end_bi + 1
    while k + 2 < end_k:
        a = movements[k]
        if a.direction != Direction.UP:
            k += 1
            continue
        b = movements[k + 1]
        if b.direction != Direction.DOWN:
            k += 1
            continue
        c = movements[k + 2]
        if c.direction != Direction.UP:
            k += 1
            continue
        hi_a = max(a.start_price, a.end_price)
        hi_c = max(c.start_price, c.end_price)
        if hi_c >= hi_a:
            k += 1
            continue
        if (hi_a - hi_c) / max(hi_a, 1e-9) < 0.001:
            k += 1
            continue
        if pivot.zd < hi_a < pivot.zg:
            k += 1
            continue
        sl = hi_a + _STOP_LOSS_BUFFER_RATIO * pivot_h
        out.append(
            _signal(
                candles=candles,
                side=SignalSide.SELL,
                kind="second_class",
                idx=c.end_idx,
                price=c.end_price,
                description="形态二卖：后段高点低于前段高点（独立检测，无需背驰）",
                strength=0.55,
                pivot_level=pivot_lv,
                pivot_idx=pivot_idx,
                entry_seg_idx=k,
                leave_seg_idx=k + 2,
                macd_ratio=None,
                evidence=f"{'笔' if pivot_lv == 'bi' else '线段'}中枢#{pivot_idx}，形态二卖 #{k}..#{k + 2}，压低{((hi_a - hi_c) / hi_a * 100):.2f}%",
                level=sig_level,
                stop_loss=sl,
                take_profit=c.end_price - 2 * (sl - c.end_price),
                take_profit_1=c.end_price - (sl - c.end_price),
            )
        )
        break  # 只取第一个匹配

    return out


def _second_extend_signal(
    candles: list[Candle],
    movements: list[Movement],
    first_signal: Signal,
    segment_idx: int,
    second: Signal,
    pivot_idx: int,
    pivots: list[Pivot],
    level: str = "bi",
) -> Optional[Signal]:
    """二买/二卖延伸（T2S）：二类确认后，同中枢至下一中枢形成前，再次出现抬高/压低结构。"""
    if not settings.enable_t2s_second_extend or pivot_idx < 0 or pivot_idx >= len(pivots):
        return None
    cur_p = pivots[pivot_idx]
    hi = _next_pivot_start_bi(pivots, pivot_idx, cur_p)
    max_i = len(movements) - 3
    if hi is not None:
        max_i = min(max_i, hi - 3)
    ref = second.price
    base = segment_idx + 3
    if base > max_i:
        return None
    if first_signal.side == SignalSide.BUY:
        for i in range(base, max_i + 1):
            retrace = movements[i + 1]
            confirm = movements[i + 2]
            if retrace.direction != Direction.UP or confirm.direction != Direction.DOWN:
                continue
            if confirm.end_price <= ref:
                continue
            if confirm.end_price <= first_signal.price:
                continue
            return _signal(
                candles=candles,
                side=SignalSide.BUY,
                kind="second_extend",
                idx=confirm.end_idx,
                price=confirm.end_price,
                description="二买延伸(T2S)：二类后再次回试抬高低点（同中枢语境，至下一中枢前）",
                strength=0.64,
                pivot_level=first_signal.pivot_level,
                pivot_idx=first_signal.pivot_idx,
                entry_seg_idx=i,
                leave_seg_idx=i + 2,
                macd_ratio=first_signal.macd_ratio,
                evidence=f"基于二类买点延伸｜枢#{pivot_idx}｜段#{i}..#{i + 2}",
                level=level,
                stop_loss=ref,
                take_profit=confirm.end_price + 2 * (confirm.end_price - ref),
                take_profit_1=confirm.end_price + (confirm.end_price - ref),
            )
        return None
    for i in range(base, max_i + 1):
        retrace = movements[i + 1]
        confirm = movements[i + 2]
        if retrace.direction != Direction.DOWN or confirm.direction != Direction.UP:
            continue
        if confirm.end_price >= ref:
            continue
        if confirm.end_price >= first_signal.price:
            continue
        return _signal(
            candles=candles,
            side=SignalSide.SELL,
            kind="second_extend",
            idx=confirm.end_idx,
            price=confirm.end_price,
            description="二卖延伸(T2S)：二类后再次反抽压低高点（同中枢语境，至下一中枢前）",
            strength=0.64,
            pivot_level=first_signal.pivot_level,
            pivot_idx=first_signal.pivot_idx,
            entry_seg_idx=i,
            leave_seg_idx=i + 2,
            macd_ratio=first_signal.macd_ratio,
            evidence=f"基于二类卖点延伸｜枢#{pivot_idx}｜段#{i}..#{i + 2}",
            level=level,
            stop_loss=ref,
            take_profit=confirm.end_price - 2 * (ref - confirm.end_price),
            take_profit_1=confirm.end_price - (ref - confirm.end_price),
        )
    return None


def _second_signal(
    candles: list[Candle],
    segments: list[Movement],
    first_signal: Signal,
    segment_idx: int,
    level: str = "bi",
) -> Optional[Signal]:
    retrace_idx = segment_idx + 1
    confirm_idx = segment_idx + 2
    if confirm_idx >= len(segments):
        return None
    retrace = segments[retrace_idx]
    confirm = segments[confirm_idx]
    if first_signal.side == SignalSide.BUY:
        if retrace.direction != Direction.UP or confirm.direction != Direction.DOWN:
            return None
        if confirm.end_price <= first_signal.price:
            return None
        return _signal(
            candles=candles,
            side=SignalSide.BUY,
            kind="second",
            idx=confirm.end_idx,
            price=confirm.end_price,
            description="二买：一买后回试不破前低，保留底背驰后的低点结构",
            strength=0.7,
            pivot_level=first_signal.pivot_level,
            pivot_idx=first_signal.pivot_idx,
            entry_seg_idx=first_signal.entry_seg_idx,
            leave_seg_idx=first_signal.leave_seg_idx,
            macd_ratio=first_signal.macd_ratio,
            evidence=f"基于一类买点：{first_signal.evidence}" if first_signal.evidence else None,
            level=level,
            stop_loss=first_signal.price,
            take_profit=confirm.end_price + 2 * (confirm.end_price - first_signal.price),
            take_profit_1=confirm.end_price + (confirm.end_price - first_signal.price),
        )

    if retrace.direction != Direction.DOWN or confirm.direction != Direction.UP:
        return None
    if confirm.end_price >= first_signal.price:
        return None
    return _signal(
        candles=candles,
        side=SignalSide.SELL,
        kind="second",
        idx=confirm.end_idx,
        price=confirm.end_price,
        description="二卖：一卖后反抽不破前高，保留顶背驰后的高点结构",
        strength=0.7,
        pivot_level=first_signal.pivot_level,
        pivot_idx=first_signal.pivot_idx,
        entry_seg_idx=first_signal.entry_seg_idx,
        leave_seg_idx=first_signal.leave_seg_idx,
        macd_ratio=first_signal.macd_ratio,
        evidence=f"基于一类卖点：{first_signal.evidence}" if first_signal.evidence else None,
        level=level,
        stop_loss=first_signal.price,
        take_profit=confirm.end_price - 2 * (first_signal.price - confirm.end_price),
        take_profit_1=confirm.end_price - (first_signal.price - confirm.end_price),
    )


def _third_signal(
    candles: list[Candle],
    segments: list[Movement],
    first_signal: Signal,
    segment_idx: int,
    pivot: Pivot,
    level: str = "bi",
) -> Optional[Signal]:
    retrace_idx = segment_idx + 1
    confirm_idx = segment_idx + 2
    if confirm_idx >= len(segments):
        return None
    retrace = segments[retrace_idx]
    confirm = segments[confirm_idx]
    if first_signal.side == SignalSide.SELL:
        if retrace.direction != Direction.DOWN or confirm.direction != Direction.UP:
            return None
        if min(retrace.start_price, retrace.end_price) <= pivot.zg:
            return None
        sl = _sl_buy_third(pivot.zd, pivot.zg)
        return _signal(
            candles=candles,
            side=SignalSide.BUY,
            kind="third",
            idx=confirm.end_idx,
            price=confirm.end_price,
            description="三买：向上离开中枢后回踩不回中枢，并再次上行确认",
            strength=0.8,
            pivot_level=first_signal.pivot_level,
            pivot_idx=first_signal.pivot_idx,
            entry_seg_idx=first_signal.entry_seg_idx,
            leave_seg_idx=first_signal.leave_seg_idx,
            macd_ratio=first_signal.macd_ratio,
            evidence=f"基于一类卖点后的离开回踩：{first_signal.evidence}" if first_signal.evidence else None,
            level=level,
            stop_loss=sl,
            take_profit=confirm.end_price + 2 * (confirm.end_price - sl),
            take_profit_1=confirm.end_price + (confirm.end_price - sl),
        )

    if retrace.direction != Direction.UP or confirm.direction != Direction.DOWN:
        return None
    if max(retrace.start_price, retrace.end_price) >= pivot.zd:
        return None
    sl = _sl_sell_third(pivot.zd, pivot.zg)
    return _signal(
        candles=candles,
        side=SignalSide.SELL,
        kind="third",
        idx=confirm.end_idx,
        price=confirm.end_price,
        description="三卖：向下离开中枢后反抽不回中枢，并再次下行确认",
        strength=0.8,
        pivot_level=first_signal.pivot_level,
        pivot_idx=first_signal.pivot_idx,
        entry_seg_idx=first_signal.entry_seg_idx,
        leave_seg_idx=first_signal.leave_seg_idx,
        macd_ratio=first_signal.macd_ratio,
        evidence=f"基于一类买点后的离开反抽：{first_signal.evidence}" if first_signal.evidence else None,
        level=level,
        stop_loss=sl,
        take_profit=confirm.end_price - 2 * (sl - confirm.end_price),
        take_profit_1=confirm.end_price - (sl - confirm.end_price),
    )


def _signal(
    candles: list[Candle],
    side: SignalSide,
    kind: str,
    idx: int,
    price: float,
    description: str,
    strength: float,
    pivot_level: Optional[str] = None,
    pivot_idx: Optional[int] = None,
    entry_seg_idx: Optional[int] = None,
    leave_seg_idx: Optional[int] = None,
    macd_ratio: Optional[float] = None,
    evidence: Optional[str] = None,
    level: str = "bi",
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    take_profit_1: Optional[float] = None,
) -> Signal:
    safe_idx = min(max(idx, 0), len(candles) - 1)
    return Signal(
        side=side,
        kind=kind,
        level=level,
        idx=safe_idx,
        time=candles[safe_idx].time,
        price=price,
        description=description,
        strength=strength,
        pivot_level=pivot_level,
        pivot_idx=pivot_idx,
        entry_seg_idx=entry_seg_idx,
        leave_seg_idx=leave_seg_idx,
        macd_ratio=macd_ratio,
        evidence=evidence,
        stop_loss=stop_loss,
        take_profit=take_profit,
        take_profit_1=take_profit_1,
    )


def _is_more_extreme(candidate: Fractal, current: Fractal) -> bool:
    if candidate.type == PointType.TOP:
        return candidate.price >= current.price
    return candidate.price <= current.price


def _breaks_previous_stroke_start(selected: list[Fractal], fractal: Fractal) -> bool:
    if len(selected) < 2:
        return False
    previous_start = selected[-2]
    return fractal.type == previous_start.type and _is_more_extreme(fractal, previous_start)


def _valid_stroke_span(
    start: Fractal,
    end: Fractal,
    min_gap: int,
    candles: Optional[list[Candle]],
) -> bool:
    if end.norm_idx - start.norm_idx < min_gap:
        return False

    if start.type == PointType.BOTTOM and end.type == PointType.TOP and end.price <= start.price:
        return False
    if start.type == PointType.TOP and end.type == PointType.BOTTOM and end.price >= start.price:
        return False
    if candles is None:
        return True

    lo = max(0, min(start.norm_idx, end.norm_idx))
    hi = min(len(candles) - 1, max(start.norm_idx, end.norm_idx))
    segment = candles[lo : hi + 1]
    if not segment:
        return False

    max_high = max(candle.high for candle in segment)
    min_low = min(candle.low for candle in segment)
    tolerance = 1e-8
    if start.type == PointType.BOTTOM:
        return abs(start.price - min_low) <= tolerance and abs(end.price - max_high) <= tolerance
    return abs(start.price - max_high) <= tolerance and abs(end.price - min_low) <= tolerance


def _ensure_source_indices(candle: Candle, fallback_idx: int) -> Candle:
    source_idx = candle.source_idx if candle.source_idx is not None else fallback_idx
    return candle.model_copy(
        update={
            "source_idx": source_idx,
            "high_idx": candle.high_idx if candle.high_idx is not None else source_idx,
            "low_idx": candle.low_idx if candle.low_idx is not None else source_idx,
        }
    )


def _find_norm_idx_by_source(candles: list[Candle], source_idx: int) -> int:
    return min(
        range(len(candles)),
        key=lambda idx: abs((candles[idx].source_idx if candles[idx].source_idx is not None else idx) - source_idx),
    )


def _pick_indexed_extreme(
    left: Candle,
    right: Candle,
    field: str,
    prefer_max: bool,
) -> tuple[float, int]:
    left_value = float(getattr(left, field))
    right_value = float(getattr(right, field))
    idx_field = f"{field}_idx"
    left_idx = int(getattr(left, idx_field) if getattr(left, idx_field) is not None else left.source_idx or 0)
    right_idx = int(getattr(right, idx_field) if getattr(right, idx_field) is not None else right.source_idx or 0)

    if prefer_max:
        return (left_value, left_idx) if left_value >= right_value else (right_value, right_idx)
    return (left_value, left_idx) if left_value <= right_value else (right_value, right_idx)


def _safe_strength(previous_area: float, current_area: float) -> float:
    if previous_area <= 0:
        return 1.0
    return max(0.0, min(1.0, 1 - (current_area / previous_area)))
