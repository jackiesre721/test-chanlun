"""缠论分析流水线：对给定 K 线序列产出 AnalyzeResponse（与行情拉取解耦）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.core.models import AnalyzeResponse, Candle, Market, Pivot, Signal, Stroke
from app.services.action_focus import build_action_focus
from app.services.analysis_cache import display_macd_for_analysis
from app.services.chan_advanced import build_chan_advanced_context
from app.services.risk_controls import enrich_signals_with_sl_tp
from app.services.chan_engine import (
    build_active_stroke,
    build_divergences,
    build_pivots,
    build_segment_pivots,
    build_segments,
    build_signals,
    build_strokes,
    build_t1p_pan_signals,
    find_fractals,
    hydrate_stroke_pause,
    normalize_candles,
)
from app.services.fake_bi import build_fake_bis
from app.services.indicators import bollinger_bands, rsi_wilder, td_sequential
from app.services.kline_hierarchy import build_kline_parent_refs
from app.services.lines_form import analyze_lines_form
from app.services.pivot_symmetry import hydrate_pivot_symmetry
from app.services.stroke_metrics import hydrate_stroke_metrics

RULES_VERSION = "strict-chan-v18"


@dataclass(frozen=True)
class AnalyzeBundle:
    response: AnalyzeResponse
    all_buy_signals: list[Signal]
    all_sell_signals: list[Signal]


def build_analyze_response(
    candles: list[Candle],
    *,
    market: Market,
    symbol: str,
    interval: str,
    higher_strokes: list[Stroke],
    higher_pivots: list[Pivot],
    warning_override: Optional[str] = None,
    higher_interval: Optional[str] = None,
    higher_candles_normalized: Optional[list[Candle]] = None,
) -> AnalyzeResponse:
    return build_analyze_bundle(
        candles,
        market=market,
        symbol=symbol,
        interval=interval,
        higher_strokes=higher_strokes,
        higher_pivots=higher_pivots,
        warning_override=warning_override,
        higher_interval=higher_interval,
        higher_candles_normalized=higher_candles_normalized,
    ).response


def build_analyze_bundle(
    candles: list[Candle],
    *,
    market: Market,
    symbol: str,
    interval: str,
    higher_strokes: list[Stroke],
    higher_pivots: list[Pivot],
    warning_override: Optional[str] = None,
    higher_interval: Optional[str] = None,
    higher_candles_normalized: Optional[list[Candle]] = None,
) -> AnalyzeBundle:
    if not candles:
        raise ValueError("candles must be non-empty")
    normalized = normalize_candles(candles)
    return build_analyze_bundle_from_normalized(
        normalized,
        market=market,
        symbol=symbol,
        interval=interval,
        higher_strokes=higher_strokes,
        higher_pivots=higher_pivots,
        warning_override=warning_override,
        higher_interval=higher_interval,
        higher_candles_normalized=higher_candles_normalized,
        source_raw_bar_count=len(candles),
    )


def build_analyze_bundle_from_normalized(
    normalized: list[Candle],
    *,
    market: Market,
    symbol: str,
    interval: str,
    higher_strokes: list[Stroke],
    higher_pivots: list[Pivot],
    warning_override: Optional[str] = None,
    higher_interval: Optional[str] = None,
    higher_candles_normalized: Optional[list[Candle]] = None,
    source_raw_bar_count: Optional[int] = None,
) -> AnalyzeBundle:
    """对已合并 K 线做一次完整分析（供增量流 `ChanIncrementalAnalyzer` 跳过重复 normalize）。"""
    if not normalized:
        raise ValueError("normalized candles must be non-empty")

    fractals = find_fractals(normalized)
    strokes = build_strokes(fractals, candles=normalized)
    strokes = hydrate_stroke_pause(strokes, normalized)
    strokes = hydrate_stroke_metrics(strokes, normalized)
    active_stroke = build_active_stroke(normalized, strokes)
    segments = build_segments(strokes)
    bi_pivots = build_pivots(strokes)
    segment_pivots = build_segment_pivots(segments)
    bi_pivots = hydrate_pivot_symmetry(bi_pivots, normalized)
    segment_pivots = hydrate_pivot_symmetry(segment_pivots, normalized)
    pivots = bi_pivots + segment_pivots

    display_macd = display_macd_for_analysis(normalized)
    boll_series = bollinger_bands(normalized)
    rsi14_series = rsi_wilder([c.close for c in normalized], 14)
    bi_divergences = build_divergences(strokes, bi_pivots, display_macd, candles=normalized)
    segment_divergences = build_divergences(segments, segment_pivots, display_macd, candles=normalized)
    divergences = bi_divergences + segment_divergences

    bi_pivots_only = [p for p in pivots if p.level == "bi"]
    lines_form = analyze_lines_form(strokes, bi_pivots_only)
    fake_bis = build_fake_bis(strokes, fractals, normalized)

    bi_buy_signals, bi_sell_signals = build_signals(
        normalized, strokes, bi_pivots, bi_divergences, trim_latest=None
    )
    segment_buy_signals, segment_sell_signals = build_signals(
        normalized, segments, segment_pivots, segment_divergences, trim_latest=None
    )
    t1p_buy, t1p_sell = (
        build_t1p_pan_signals(normalized, strokes, display_macd) if not bi_pivots else ([], [])
    )
    all_buy = sorted(bi_buy_signals + segment_buy_signals + t1p_buy, key=lambda s: s.idx)
    all_sell = sorted(bi_sell_signals + segment_sell_signals + t1p_sell, key=lambda s: s.idx)
    all_buy = enrich_signals_with_sl_tp(all_buy, fractals, pivots)
    all_sell = enrich_signals_with_sl_tp(all_sell, fractals, pivots)
    buy_signals = all_buy[-12:]
    sell_signals = all_sell[-12:]

    last_i = len(normalized) - 1
    action_focus = build_action_focus(
        current_price=normalized[-1].close,
        last_bar_index=last_i,
        kline_count=len(normalized),
        zhongshus=pivots,
        zhongshus_lv2=higher_pivots,
        active_bi=active_stroke,
        divergences=divergences,
        buy_signals=all_buy,
        sell_signals=all_sell,
    )
    td = td_sequential(normalized)

    kline_refs = (
        build_kline_parent_refs(normalized, higher_candles_normalized, higher_interval)
        if higher_interval and higher_candles_normalized
        else []
    )
    raw_n = source_raw_bar_count if source_raw_bar_count is not None else len(normalized)
    warning = warning_override
    if warning is None:
        warning = _warning_for(market, raw_n, len(strokes))

    advanced_context = build_chan_advanced_context(
        base_interval=interval,
        candles=normalized,
        bis=strokes,
        bi_pivots=bi_pivots,
        segments=segments,
        segment_pivots=segment_pivots,
        higher_interval=higher_interval,
        higher_strokes=higher_strokes,
        segment_engine=settings.segment_engine,
    )

    response = AnalyzeResponse(
        market=market,
        symbol=symbol,
        interval=interval,
        current_price=normalized[-1].close,
        data_source="Binance spot",
        rules_version=RULES_VERSION,
        segment_engine=settings.segment_engine,
        lines_form=lines_form,
        kline_data=normalized,
        macd_data=display_macd,
        bollinger=boll_series,
        rsi14=rsi14_series,
        fractals=fractals,
        bis=strokes,
        active_bi=active_stroke,
        segments=segments,
        divergences=divergences,
        bis_lv2=higher_strokes,
        zhongshus=pivots,
        zhongshus_lv2=higher_pivots,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        td_summary=td,
        action_focus=action_focus,
        warning=warning,
        advanced_context=advanced_context,
        kline_parent_refs=kline_refs,
        fake_bis=fake_bis,
    )
    return AnalyzeBundle(response=response, all_buy_signals=all_buy, all_sell_signals=all_sell)


def _warning_for(market: Market, candle_count: int, stroke_count: int) -> Optional[str]:
    if market != Market.CRYPTO:
        return "当前 MVP 仅实现数字货币市场。"
    if candle_count < 200:
        return "K 线数量偏少，分型和背驰稳定性会下降。"
    if stroke_count < 6:
        return "当前周期可用笔较少，买卖点仅供观察。"
    return None
