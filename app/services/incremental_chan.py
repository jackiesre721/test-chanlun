"""真·增量：单根 Bar 喂入时只做包含合并状态更新 + 一次 `build_analyze_bundle_from_normalized`（不重扫原始全历史做 normalize）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.models import Candle, Market, Pivot, Stroke
from app.services.analysis_pipeline import AnalyzeBundle, build_analyze_bundle_from_normalized
from app.services.chan_engine import CandleNormalizeState, normalize_stream_push


@dataclass
class ChanIncrementalAnalyzer:
    """维护 `CandleNormalizeState`；每 `update` 追加一根原始 K 并重算分析包。"""

    market: Market
    symbol: str
    interval: str
    higher_strokes: list[Stroke] = field(default_factory=list)
    higher_pivots: list[Pivot] = field(default_factory=list)
    higher_interval: Optional[str] = None
    higher_candles_normalized: Optional[list[Candle]] = None
    _norm_state: CandleNormalizeState = field(default_factory=CandleNormalizeState)
    _raw_count: int = 0

    def reset(self) -> None:
        self._norm_state = CandleNormalizeState()
        self._raw_count = 0

    def update(self, bar: Candle) -> AnalyzeBundle:
        normalize_stream_push(self._norm_state, bar, self._raw_count)
        self._raw_count += 1
        norm = list(self._norm_state.normalized)
        return build_analyze_bundle_from_normalized(
            norm,
            market=self.market,
            symbol=self.symbol,
            interval=self.interval,
            higher_strokes=self.higher_strokes,
            higher_pivots=self.higher_pivots,
            warning_override=None,
            higher_interval=self.higher_interval,
            higher_candles_normalized=self.higher_candles_normalized,
            source_raw_bar_count=self._raw_count,
        )
