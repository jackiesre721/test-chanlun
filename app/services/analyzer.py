from typing import Optional

from app.core.config import settings
from app.core.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Candle,
    MultiAnalyzeRequest,
    MultiAnalyzeResponse,
    MultiAnalyzeResultRow,
    Pivot,
    Stroke,
)
from app.core.errors import MarketDataError
from app.repositories.market_data import BinanceRepository
from app.services.analyze_disk_cache import load_cached_analyze_result, save_cached_analyze_result
from app.services.analysis_pipeline import build_analyze_response

HIGHER_INTERVAL = {
    "1": "15",
    "15": "30",
    "30": "60",
    "60": "240",
    "240": "1440",
}


class AnalyzerService:
    """Business service for Chan analysis."""

    def __init__(self, market_data: BinanceRepository) -> None:
        self._market_data = market_data

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        anchor_ms: Optional[int] = None
        if settings.analyze_disk_cache_enabled and request.glm_verdict is None:
            try:
                tip = await self._market_data.get_klines(request.symbol, request.interval, limit=1)
                if tip:
                    anchor_ms = int(tip[-1].open_time)
                    cached = load_cached_analyze_result(
                        request=request,
                        eff_limit=request.limit,
                        anchor_open_time_ms=anchor_ms,
                    )
                    if cached is not None:
                        return cached
            except MarketDataError:
                anchor_ms = None

        candles = await self._market_data.get_klines(
            symbol=request.symbol,
            interval=request.interval,
            limit=request.limit,
        )
        higher_strokes, higher_pivots, higher_norm = await self._analyze_higher_level(request, candles)
        result = build_analyze_response(
            candles,
            market=request.market,
            symbol=request.symbol,
            interval=request.interval,
            higher_strokes=higher_strokes,
            higher_pivots=higher_pivots,
            higher_interval=HIGHER_INTERVAL.get(request.interval),
            higher_candles_normalized=higher_norm,
        )
        if request.glm_verdict is not None:
            from app.services.ai_glm_verdict import verdict_from_analyze_payload

            body = result.model_dump(mode="json")
            g = request.glm_verdict
            if g.glm_api_key:
                body["glm_api_key"] = g.glm_api_key
            if g.glm_model:
                body["glm_model"] = g.glm_model
            body["glm_full_context"] = g.glm_full_context
            glm_out = await verdict_from_analyze_payload(body)
            result = result.model_copy(update={"glm_verdict": glm_out})
        save_anchor = anchor_ms
        if save_anchor is None and result.kline_data:
            save_anchor = int(result.kline_data[-1].open_time)
        if save_anchor is not None:
            save_cached_analyze_result(
                request=request,
                eff_limit=request.limit,
                anchor_open_time_ms=save_anchor,
                response=result,
            )
        return result

    async def analyze_multi(self, request: MultiAnalyzeRequest) -> MultiAnalyzeResponse:
        rows: list[MultiAnalyzeResultRow] = []
        for interval in request.intervals:
            single = AnalyzeRequest(
                market=request.market,
                symbol=request.symbol,
                interval=interval,
                limit=request.limit,
            )
            rows.append(MultiAnalyzeResultRow(interval=interval, result=await self.analyze(single)))
        return MultiAnalyzeResponse(market=request.market, symbol=request.symbol, results=rows)

    async def _analyze_higher_level(
        self,
        request: AnalyzeRequest,
        base_candles: list[Candle],
    ) -> tuple[list[Stroke], list[Pivot], Optional[list[Candle]]]:
        higher_interval = HIGHER_INTERVAL.get(request.interval)
        if higher_interval is None:
            return [], [], None

        higher_limit = max(120, min(1000, request.limit // 3))
        try:
            higher_candles = await self._market_data.get_klines(
                symbol=request.symbol,
                interval=higher_interval,
                limit=higher_limit,
            )
        except MarketDataError:
            return [], [], None
        from app.services.chan_engine import (
            build_pivots,
            build_segment_pivots,
            build_segments,
            build_strokes,
            find_fractals,
            normalize_candles,
        )

        higher_normalized = normalize_candles(higher_candles)
        base_normalized = normalize_candles(base_candles)
        higher_strokes = build_strokes(find_fractals(higher_normalized), candles=higher_normalized)
        higher_segments = build_segments(higher_strokes)
        higher_pivots = build_pivots(higher_strokes) + build_segment_pivots(higher_segments)
        return (
            [_map_stroke_to_base(stroke, higher_normalized, base_normalized) for stroke in higher_strokes],
            [_map_pivot_to_base(pivot, higher_normalized, base_normalized) for pivot in higher_pivots],
            higher_normalized,
        )


def _map_stroke_to_base(stroke: Stroke, higher_norm: list[Candle], base_norm: list[Candle]) -> Stroke:
    hi_lo = min(stroke.start_idx, stroke.end_idx)
    hi_hi = max(stroke.start_idx, stroke.end_idx)
    hi_lo = max(0, min(hi_lo, len(higher_norm) - 1)) if higher_norm else 0
    hi_hi = max(0, min(hi_hi, len(higher_norm) - 1)) if higher_norm else 0
    t_lo = higher_norm[hi_lo].open_time if higher_norm else None
    t_hi = higher_norm[hi_hi].open_time if higher_norm else None
    return stroke.model_copy(
        update={
            "start_idx": _map_higher_index_to_base(stroke.start_idx, stroke.start_price, higher_norm, base_norm),
            "end_idx": _map_higher_index_to_base(stroke.end_idx, stroke.end_price, higher_norm, base_norm),
            "higher_origin_bar_lo": hi_lo,
            "higher_origin_bar_hi": hi_hi,
            "higher_origin_open_time_lo": t_lo,
            "higher_origin_open_time_hi": t_hi,
        }
    )


def _map_pivot_to_base(pivot: Pivot, higher_norm: list[Candle], base_norm: list[Candle]) -> Pivot:
    return pivot.model_copy(
        update={
            "start_idx": _map_higher_index_to_base(pivot.start_idx, pivot.zd, higher_norm, base_norm),
            "end_idx": _map_higher_index_to_base(pivot.end_idx, pivot.zg, higher_norm, base_norm),
        }
    )


def _map_higher_index_to_base(
    higher_idx: int,
    price: float,
    higher_candles: list[Candle],
    base_candles: list[Candle],
) -> int:
    """将上级（已标准化）K 线索引映射到本级标准化 K 线索引：半开时间区间 [open_time, next.open_time)。"""
    if not higher_candles or not base_candles:
        return 0
    safe_idx = min(max(higher_idx, 0), len(higher_candles) - 1)
    start_time = higher_candles[safe_idx].open_time
    end_time = higher_candles[safe_idx + 1].open_time if safe_idx + 1 < len(higher_candles) else start_time + 1
    candidates = [
        idx for idx, candle in enumerate(base_candles) if start_time <= candle.open_time < end_time
    ]
    if not candidates:
        return min(range(len(base_candles)), key=lambda idx: abs(base_candles[idx].open_time - start_time))
    return min(candidates, key=lambda idx: min(abs(base_candles[idx].high - price), abs(base_candles[idx].low - price)))
