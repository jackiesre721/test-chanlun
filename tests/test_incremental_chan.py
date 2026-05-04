from __future__ import annotations

from app.core.models import Candle, Market
from app.services.analysis_pipeline import build_analyze_bundle
from app.services.incremental_chan import ChanIncrementalAnalyzer


def _bar(i: int) -> Candle:
    t = 1_000_000 + i * 60_000
    o = 1.0 + i * 0.02
    return Candle(open_time=t, time=str(t), open=o, high=o + 0.4, low=o - 0.25, close=o + 0.1, volume=1.0)


def test_incremental_last_bar_matches_batch() -> None:
    raw = [_bar(i) for i in range(80)]
    inc = ChanIncrementalAnalyzer(market=Market.CRYPTO, symbol="BTCUSDT", interval="60")
    bundle = None
    for c in raw:
        bundle = inc.update(c)
    assert bundle is not None
    batch = build_analyze_bundle(
        raw,
        market=Market.CRYPTO,
        symbol="BTCUSDT",
        interval="60",
        higher_strokes=[],
        higher_pivots=[],
    )
    assert len(bundle.response.kline_data) == len(batch.response.kline_data)
    assert len(bundle.response.macd_data) == len(batch.response.macd_data)
    assert len(bundle.response.fake_bis) == len(batch.response.fake_bis)
