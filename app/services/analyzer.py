from typing import Optional

from app.core.models import AnalyzeRequest, AnalyzeResponse, Candle, Market, Pivot, Stroke
from app.core.errors import MarketDataError
from app.repositories.market_data import BinanceRepository
from app.services.chan_engine import (
    build_active_stroke,
    build_divergences,
    build_segment_pivots,
    build_segments,
    build_signals,
    build_pivots,
    build_strokes,
    find_fractals,
    normalize_candles,
)
from app.services.action_focus import build_action_focus
from app.services.indicators import td_sequential, macd

RULES_VERSION = "strict-chan-v5"

HIGHER_INTERVAL = {
    "1": "15",
    "15": "30",
}


class AnalyzerService:
    """Business service for Chan analysis."""

    def __init__(self, market_data: BinanceRepository) -> None:
        self._market_data = market_data

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        candles = await self._market_data.get_klines(
            symbol=request.symbol,
            interval=request.interval,
            limit=request.limit,
        )
        normalized = normalize_candles(candles)
        fractals = find_fractals(normalized)
        strokes = build_strokes(fractals, candles=normalized)
        active_stroke = build_active_stroke(normalized, strokes)
        segments = build_segments(strokes)
        bi_pivots = build_pivots(strokes)
        segment_pivots = build_segment_pivots(segments)
        pivots = bi_pivots + segment_pivots
        higher_strokes, higher_pivots = await self._analyze_higher_level(request, candles)
        display_macd = macd(candles)
        bi_divergences = build_divergences(strokes, bi_pivots, display_macd)
        segment_divergences = build_divergences(segments, segment_pivots, display_macd)
        divergences = bi_divergences + segment_divergences
        bi_buy_signals, bi_sell_signals = build_signals(candles, strokes, bi_pivots, bi_divergences)
        segment_buy_signals, segment_sell_signals = build_signals(candles, segments, segment_pivots, segment_divergences)
        all_buy = sorted(bi_buy_signals + segment_buy_signals, key=lambda s: s.idx)
        all_sell = sorted(bi_sell_signals + segment_sell_signals, key=lambda s: s.idx)
        buy_signals = all_buy[-12:]
        sell_signals = all_sell[-12:]
        last_i = len(candles) - 1
        action_focus = build_action_focus(
            current_price=candles[-1].close,
            last_bar_index=last_i,
            kline_count=len(candles),
            zhongshus=pivots,
            zhongshus_lv2=higher_pivots,
            active_bi=active_stroke,
            divergences=divergences,
            buy_signals=all_buy,
            sell_signals=all_sell,
        )
        td = td_sequential(candles)

        return AnalyzeResponse(
            market=request.market,
            symbol=request.symbol,
            interval=request.interval,
            current_price=candles[-1].close,
            data_source="Binance spot",
            rules_version=RULES_VERSION,
            kline_data=candles,
            macd_data=display_macd,
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
            warning=_warning_for(request.market, len(candles), len(strokes)),
        )

    async def _analyze_higher_level(
        self,
        request: AnalyzeRequest,
        base_candles: list[Candle],
    ) -> tuple[list[Stroke], list[Pivot]]:
        higher_interval = HIGHER_INTERVAL.get(request.interval)
        if higher_interval is None:
            return [], []

        higher_limit = max(120, min(1000, request.limit // 3))
        try:
            higher_candles = await self._market_data.get_klines(
                symbol=request.symbol,
                interval=higher_interval,
                limit=higher_limit,
            )
        except MarketDataError:
            return [], []
        higher_normalized = normalize_candles(higher_candles)
        higher_strokes = build_strokes(find_fractals(higher_normalized), candles=higher_normalized)
        higher_segments = build_segments(higher_strokes)
        higher_pivots = build_pivots(higher_strokes) + build_segment_pivots(higher_segments)
        return (
            [_map_stroke_to_base(stroke, higher_candles, base_candles) for stroke in higher_strokes],
            [_map_pivot_to_base(pivot, higher_candles, base_candles) for pivot in higher_pivots],
        )


def _map_stroke_to_base(stroke: Stroke, higher_candles: list[Candle], base_candles: list[Candle]) -> Stroke:
    return stroke.model_copy(
        update={
            "start_idx": _map_higher_index_to_base(stroke.start_idx, stroke.start_price, higher_candles, base_candles),
            "end_idx": _map_higher_index_to_base(stroke.end_idx, stroke.end_price, higher_candles, base_candles),
        }
    )


def _map_pivot_to_base(pivot: Pivot, higher_candles: list[Candle], base_candles: list[Candle]) -> Pivot:
    return pivot.model_copy(
        update={
            "start_idx": _map_higher_index_to_base(pivot.start_idx, pivot.zd, higher_candles, base_candles),
            "end_idx": _map_higher_index_to_base(pivot.end_idx, pivot.zg, higher_candles, base_candles),
        }
    )


def _map_higher_index_to_base(
    higher_idx: int,
    price: float,
    higher_candles: list[Candle],
    base_candles: list[Candle],
) -> int:
    safe_idx = min(max(higher_idx, 0), len(higher_candles) - 1)
    start_time = higher_candles[safe_idx].open_time
    end_time = higher_candles[safe_idx + 1].open_time if safe_idx + 1 < len(higher_candles) else start_time + 1
    candidates = [
        idx
        for idx, candle in enumerate(base_candles)
        if start_time <= candle.open_time < end_time
    ]
    if not candidates:
        return min(
            range(len(base_candles)),
            key=lambda idx: abs(base_candles[idx].open_time - start_time),
        )
    return min(
        candidates,
        key=lambda idx: min(abs(base_candles[idx].high - price), abs(base_candles[idx].low - price)),
    )


def _warning_for(market: Market, candle_count: int, stroke_count: int) -> Optional[str]:
    if market != Market.CRYPTO:
        return "当前 MVP 仅实现数字货币市场。"
    if candle_count < 200:
        return "K 线数量偏少，分型和背驰稳定性会下降。"
    if stroke_count < 6:
        return "当前周期可用笔较少，买卖点仅供观察。"
    return None
