from __future__ import annotations

from app.core.models import Candle
from app.services.kline_hierarchy import build_kline_parent_refs


def _c(t: int) -> Candle:
    return Candle(open_time=t, time=str(t), open=1.0, high=2.0, low=0.5, close=1.0, volume=1.0)


def test_parent_ref_aligns_base_to_higher_open_time() -> None:
    higher = [_c(1_000_000 + i * 300_000) for i in range(5)]
    base = [_c(1_000_000 + i * 60_000) for i in range(25)]
    refs = build_kline_parent_refs(base, higher, "300s")
    assert len(refs) == len(base)
    assert refs[0].parent_norm_idx == 0
    assert refs[0].parent_open_time == higher[0].open_time
    # 第四根上级 K 覆盖区间内的最后一根 base 应指回 parent_norm_idx 3
    lo = higher[3].open_time
    hi = higher[4].open_time
    last_in = max(i for i, b in enumerate(base) if lo <= b.open_time < hi)
    assert refs[last_in].parent_norm_idx == 3
