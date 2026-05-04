"""本级与上级标准化 K 的父子时间对齐。"""

from __future__ import annotations

from app.core.models import Candle, KlineParentRef


def build_kline_parent_refs(
    base: list[Candle],
    higher: list[Candle],
    parent_interval: str,
) -> list[KlineParentRef]:
    """每桶本级 K 落在哪根上级 K 的 [open_time, next.open_time) 内。"""
    if not base or not higher:
        return []
    out: list[KlineParentRef] = []
    j = 0
    for i, b in enumerate(base):
        t = b.open_time
        while j + 1 < len(higher) and higher[j + 1].open_time <= t:
            j += 1
        hj = min(j, len(higher) - 1)
        hc = higher[hj]
        out.append(
            KlineParentRef(
                base_idx=i,
                parent_interval=parent_interval,
                parent_open_time=hc.open_time,
                parent_norm_idx=hj,
            )
        )
    return out
