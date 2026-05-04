from __future__ import annotations

from app.core.models import Candle
from app.services.chan_engine import CandleNormalizeState, normalize_candles, normalize_stream_push
from app.services.chan_stream import rebuild_normalized_from_raw


def _bar(i: int, o: float, h: float, l_: float, c: float) -> Candle:
    t = 1_000_000 + i * 60_000
    return Candle(open_time=t, time=str(t), open=o, high=h, low=l_, close=c, volume=1.0)


def test_stream_push_matches_batch_normalize() -> None:
    raw = [
        _bar(0, 10, 11, 9.5, 10.5),
        _bar(1, 10.4, 10.8, 10.2, 10.6),
        _bar(2, 10.5, 12, 10.4, 11.8),
        _bar(3, 11.7, 11.9, 11.0, 11.2),
        _bar(4, 11.3, 11.5, 10.8, 11.0),
    ]
    st = CandleNormalizeState()
    for i, c in enumerate(raw):
        normalize_stream_push(st, c, i)
    batch = normalize_candles(raw)
    assert [x.open_time for x in st.normalized] == [x.open_time for x in batch]
    assert [x.close for x in st.normalized] == [x.close for x in batch]


def test_rebuild_normalized_from_raw_helper() -> None:
    raw = [_bar(i, 1.0 + i * 0.1, 2.0 + i * 0.109, 0.4 + i * 0.088, 1.05 + i * 0.1) for i in range(30)]
    assert rebuild_normalized_from_raw(raw) == normalize_candles(raw)
