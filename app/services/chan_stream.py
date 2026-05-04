"""虚拟笔 / 流式 K：追加或回滚后重算；可选用增量合并或减少重复 normalize。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.models import Candle, Market, Pivot, Stroke
from app.services.analysis_pipeline import AnalyzeBundle, build_analyze_bundle
from app.services.chan_engine import CandleNormalizeState, normalize_stream_push
from app.services.incremental_chan import ChanIncrementalAnalyzer


@dataclass
class ChanVirtualPenSession:
    """持有原始 K 序列；`pop_last` 后 `rebuild_bundle` 全量重算（与单次 analyze 一致）。"""

    market: Market
    symbol: str
    interval: str
    higher_strokes: list[Stroke] = field(default_factory=list)
    higher_pivots: list[Pivot] = field(default_factory=list)
    higher_interval: Optional[str] = None
    higher_candles_normalized: Optional[list[Candle]] = None
    _raw: list[Candle] = field(default_factory=list)

    def push(self, candle: Candle) -> None:
        self._raw.append(candle)

    def pop_last(self) -> Optional[Candle]:
        if not self._raw:
            return None
        return self._raw.pop()

    def replace_all(self, candles: list[Candle]) -> None:
        self._raw = list(candles)

    @property
    def candles(self) -> list[Candle]:
        return self._raw

    def rebuild_bundle(self) -> AnalyzeBundle:
        if not self._raw:
            raise ValueError("candles must be non-empty")
        return build_analyze_bundle(
            self._raw,
            market=self.market,
            symbol=self.symbol,
            interval=self.interval,
            higher_strokes=self.higher_strokes,
            higher_pivots=self.higher_pivots,
            warning_override=None,
            higher_interval=self.higher_interval,
            higher_candles_normalized=self.higher_candles_normalized,
        )


def rebuild_normalized_from_raw(raw: list[Candle]) -> list[Candle]:
    """回滚/批量编辑后，用流式状态重放得到与 `normalize_candles` 一致的合并序列。"""
    st = CandleNormalizeState()
    for i, c in enumerate(raw):
        normalize_stream_push(st, c, i)
    return list(st.normalized)


__all__ = [
    "ChanVirtualPenSession",
    "ChanIncrementalAnalyzer",
    "rebuild_normalized_from_raw",
]
