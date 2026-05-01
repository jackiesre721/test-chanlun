from typing import Optional

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
from app.services.indicators import macd_area


def normalize_candles(candles: list[Candle]) -> list[Candle]:
    """Merge inclusion candles while preserving chronological order."""
    normalized: list[Candle] = []
    direction: Optional[Direction] = None

    for raw_idx, raw_candle in enumerate(candles):
        candle = _ensure_source_indices(raw_candle, raw_idx)
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
            normalized.append(candle)
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
                }
            )
        normalized[-1] = merged

    return normalized


def find_fractals(candles: list[Candle]) -> list[Fractal]:
    fractals: list[Fractal] = []
    for idx in range(1, len(candles) - 1):
        prev_candle = candles[idx - 1]
        candle = candles[idx]
        next_candle = candles[idx + 1]
        if candle.high > prev_candle.high and candle.high > next_candle.high:
            source_idx = candle.high_idx if candle.high_idx is not None else idx
            fractals.append(Fractal(idx=source_idx, norm_idx=idx, type=PointType.TOP, price=candle.high, time=candle.time))
        elif candle.low < prev_candle.low and candle.low < next_candle.low:
            source_idx = candle.low_idx if candle.low_idx is not None else idx
            fractals.append(Fractal(idx=source_idx, norm_idx=idx, type=PointType.BOTTOM, price=candle.low, time=candle.time))
    return fractals


STRICT_MIN_STROKE_SPAN = 4  # 5 normalized candles including both fractal candles.


def build_strokes(
    fractals: list[Fractal],
    min_gap: int = STRICT_MIN_STROKE_SPAN,
    candles: Optional[list[Candle]] = None,
) -> list[Stroke]:
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
                start_idx=start.idx,
                end_idx=end.idx,
                norm_start_idx=start.norm_idx,
                norm_end_idx=end.norm_idx,
                start_price=start.price,
                end_price=end.price,
                direction=direction,
            )
        )
    return strokes


def build_segments(strokes: list[Stroke]) -> list[Segment]:
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
                )
            )
            i += 3
        else:
            i += 1
    return pivots


def build_segment_pivots(segments: list[Segment]) -> list[Pivot]:
    pivots: list[Pivot] = []
    i = 0
    while i <= len(segments) - 5:
        entry = segments[i]
        core = segments[i + 1 : i + 4]
        overlap = _range_overlap(core)
        if overlap is None:
            i += 1
            continue

        zd, zg = overlap
        core_end = i + 3
        leaving_idx = core_end + 1
        while leaving_idx < len(segments) and _segment_overlaps_range(segments[leaving_idx], zd, zg):
            next_overlap = _range_overlap([_range_proxy(zd, zg), segments[leaving_idx]])
            if next_overlap is None:
                break
            zd, zg = next_overlap
            core_end = leaving_idx
            leaving_idx += 1

        if leaving_idx >= len(segments):
            break
        leaving = segments[leaving_idx]
        if entry.direction != leaving.direction or not _leaves_pivot_range(leaving, zd, zg):
            i += 1
            continue

        pivots.append(
            Pivot(
                start_bi=i + 1,
                end_bi=core_end,
                start_idx=segments[i + 1].start_idx,
                end_idx=segments[core_end].end_idx,
                zg=zg,
                zd=zd,
                entry_seg_idx=i,
                leave_seg_idx=leaving_idx,
                direction=leaving.direction,
            )
        )
        i = leaving_idx
    return pivots


def build_active_stroke(candles: list[Candle], strokes: list[Stroke]) -> Optional[Stroke]:
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
        end_idx = end_candle.high_idx if end_candle.high_idx is not None else end_candle.source_idx
        end_price = end_candle.high
        direction = Direction.UP
        if end_norm_idx == start_norm_idx or end_idx is None or end_price <= last.end_price:
            return None
    else:
        end_offset, end_candle = min(enumerate(segment), key=lambda item: item[1].low)
        end_norm_idx = start_norm_idx + end_offset
        end_idx = end_candle.low_idx if end_candle.low_idx is not None else end_candle.source_idx
        end_price = end_candle.low
        direction = Direction.DOWN
        if end_norm_idx == start_norm_idx or end_idx is None or end_price >= last.end_price:
            return None

    return Stroke(
        start_idx=last.end_idx,
        end_idx=end_idx,
        norm_start_idx=last.norm_end_idx,
        norm_end_idx=end_norm_idx,
        start_price=last.end_price,
        end_price=end_price,
        direction=direction,
    )


def build_divergences(
    segments: list[Segment],
    pivots: list[Pivot],
    macd_points: list[MacdPoint],
) -> list[Divergence]:
    divergences: list[Divergence] = []
    for pivot_idx, pivot in enumerate(pivots):
        leaving_idx = pivot.leave_seg_idx if pivot.leave_seg_idx is not None else _first_leaving_segment_index(segments, pivot)
        entry_idx = pivot.entry_seg_idx if pivot.entry_seg_idx is not None else pivot.start_bi - 1
        if leaving_idx is None or entry_idx < 0 or leaving_idx >= len(segments) or entry_idx >= len(segments):
            continue

        leaving = segments[leaving_idx]
        entry = segments[entry_idx]
        if entry.direction != leaving.direction or not _leaves_pivot_range(leaving, pivot.zd, pivot.zg):
            continue

        entry_area = segment_macd_area(macd_points, entry)
        leave_area = segment_macd_area(macd_points, leaving)
        if entry_area <= 0:
            continue
        ratio = leave_area / entry_area
        if ratio >= 0.8:
            continue
        if leaving.direction == Direction.DOWN and leaving.end_price >= entry.end_price:
            continue
        if leaving.direction == Direction.UP and leaving.end_price <= entry.end_price:
            continue

        divergences.append(
            Divergence(
                direction=leaving.direction,
                pivot_idx=pivot_idx,
                entry_seg_idx=entry_idx,
                leave_seg_idx=leaving_idx,
                idx=leaving.end_idx,
                price=leaving.end_price,
                entry_area=entry_area,
                leave_area=leave_area,
                ratio=ratio,
                description=f"离开段 MACD 面积/进入段={ratio:.2f}",
            )
        )
    return divergences


def build_signals(
    candles: list[Candle],
    segments: list[Segment],
    pivots: list[Pivot],
    divergences: list[Divergence],
) -> tuple[list[Signal], list[Signal]]:
    buy_signals: list[Signal] = []
    sell_signals: list[Signal] = []

    first_signal_segments: list[tuple[Signal, int, Pivot]] = []
    for divergence in divergences:
        if divergence.pivot_idx >= len(pivots):
            continue
        pivot = pivots[divergence.pivot_idx]
        strength = _safe_strength(divergence.entry_area, divergence.leave_area)
        evidence = (
            f"中枢#{divergence.pivot_idx}，进入段#{divergence.entry_seg_idx}，"
            f"离开段#{divergence.leave_seg_idx}，MACD面积比={divergence.ratio:.2f}"
        )

        if divergence.direction == Direction.DOWN:
            signal = _signal(
                candles=candles,
                side=SignalSide.BUY,
                kind="first",
                idx=divergence.idx,
                price=divergence.price,
                description=f"一买候选：向下离开中枢后价格新低，{divergence.description}，出现底背驰",
                strength=strength,
                pivot_idx=divergence.pivot_idx,
                entry_seg_idx=divergence.entry_seg_idx,
                leave_seg_idx=divergence.leave_seg_idx,
                macd_ratio=divergence.ratio,
                evidence=evidence,
            )
            buy_signals.append(signal)
            first_signal_segments.append((signal, divergence.leave_seg_idx, pivot))
        elif divergence.direction == Direction.UP:
            signal = _signal(
                candles=candles,
                side=SignalSide.SELL,
                kind="first",
                idx=divergence.idx,
                price=divergence.price,
                description=f"一卖候选：向上离开中枢后价格新高，{divergence.description}，出现顶背驰",
                strength=strength,
                pivot_idx=divergence.pivot_idx,
                entry_seg_idx=divergence.entry_seg_idx,
                leave_seg_idx=divergence.leave_seg_idx,
                macd_ratio=divergence.ratio,
                evidence=evidence,
            )
            sell_signals.append(signal)
            first_signal_segments.append((signal, divergence.leave_seg_idx, pivot))

    for first_signal, segment_idx, pivot in first_signal_segments:
        second = _second_signal(candles, segments, first_signal, segment_idx)
        if second is not None:
            (buy_signals if second.side == SignalSide.BUY else sell_signals).append(second)
        third = _third_signal(candles, segments, first_signal, segment_idx, pivot)
        if third is not None:
            (buy_signals if third.side == SignalSide.BUY else sell_signals).append(third)

    return buy_signals[-12:], sell_signals[-12:]


def segment_macd_area(points: list[MacdPoint], segment: Segment) -> float:
    return macd_area(points, segment.start_idx, segment.end_idx)


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


def _range_overlap(items: list[Segment]) -> Optional[tuple[float, float]]:
    if not items:
        return None
    lows = [min(item.start_price, item.end_price) for item in items]
    highs = [max(item.start_price, item.end_price) for item in items]
    zd = max(lows)
    zg = min(highs)
    if zd < zg:
        return zd, zg
    return None


def _segment_overlaps_range(segment: Segment, zd: float, zg: float) -> bool:
    low = min(segment.start_price, segment.end_price)
    high = max(segment.start_price, segment.end_price)
    return max(low, zd) < min(high, zg)


def _leaves_pivot_range(segment: Segment, zd: float, zg: float) -> bool:
    if segment.direction == Direction.UP:
        return segment.end_price > zg
    return segment.end_price < zd


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


def _first_leaving_segment_index(segments: list[Segment], pivot: Pivot) -> Optional[int]:
    for idx in range(pivot.end_bi + 1, len(segments)):
        segment = segments[idx]
        if segment.direction == Direction.UP and segment.end_price > pivot.zg:
            return idx
        if segment.direction == Direction.DOWN and segment.end_price < pivot.zd:
            return idx
    return None


def _second_signal(
    candles: list[Candle],
    segments: list[Segment],
    first_signal: Signal,
    segment_idx: int,
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
    )


def _third_signal(
    candles: list[Candle],
    segments: list[Segment],
    first_signal: Signal,
    segment_idx: int,
    pivot: Pivot,
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
        return _signal(
            candles=candles,
            side=SignalSide.BUY,
            kind="third",
            idx=confirm.end_idx,
            price=confirm.end_price,
            description="三买：向上离开中枢后回踩不回中枢，并再次上行确认",
            strength=0.8,
        )

    if retrace.direction != Direction.UP or confirm.direction != Direction.DOWN:
        return None
    if max(retrace.start_price, retrace.end_price) >= pivot.zd:
        return None
    return _signal(
        candles=candles,
        side=SignalSide.SELL,
        kind="third",
        idx=confirm.end_idx,
        price=confirm.end_price,
        description="三卖：向下离开中枢后反抽不回中枢，并再次下行确认",
        strength=0.8,
    )


def _signal(
    candles: list[Candle],
    side: SignalSide,
    kind: str,
    idx: int,
    price: float,
    description: str,
    strength: float,
    pivot_idx: Optional[int] = None,
    entry_seg_idx: Optional[int] = None,
    leave_seg_idx: Optional[int] = None,
    macd_ratio: Optional[float] = None,
    evidence: Optional[str] = None,
) -> Signal:
    safe_idx = min(max(idx, 0), len(candles) - 1)
    return Signal(
        side=side,
        kind=kind,
        idx=safe_idx,
        time=candles[safe_idx].time,
        price=price,
        description=description,
        strength=strength,
        pivot_idx=pivot_idx,
        entry_seg_idx=entry_seg_idx,
        leave_seg_idx=leave_seg_idx,
        macd_ratio=macd_ratio,
        evidence=evidence,
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
