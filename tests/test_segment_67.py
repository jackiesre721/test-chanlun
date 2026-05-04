"""67 课线段划分（strict67）与 legacy 切换。"""

import pytest

from app.core.models import Direction, Stroke
from app.services.chan_engine import (
    _FeatBar,
    _normalize_feat_bars_include,
    _resolve_feature_top_segment_end,
    build_segments,
)


def _stroke(i: int, direction: Direction, sp: float, ep: float) -> Stroke:
    return Stroke(
        start_idx=i,
        end_idx=i,
        norm_start_idx=i,
        norm_end_idx=i,
        start_price=sp,
        end_price=ep,
        direction=direction,
    )


def test_strict67_ends_up_segment_on_feature_top_fractal_case1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.segment_engine", "strict67", raising=False)
    # 向上线段：特征序列 X1,X3,X5 为向下笔区间，构成顶分型且一二元素有重叠（情形一）
    strokes = [
        _stroke(0, Direction.UP, 100.0, 110.0),
        _stroke(1, Direction.DOWN, 110.0, 108.5),  # [108.5,110]
        _stroke(2, Direction.UP, 108.5, 120.0),
        _stroke(3, Direction.DOWN, 120.0, 109.5),  # [109.5,120] 顶分型中间
        _stroke(4, Direction.UP, 109.5, 118.0),
        _stroke(5, Direction.DOWN, 118.0, 107.0),  # [107,118]
        _stroke(6, Direction.UP, 107.0, 120.0),
    ]
    segs = build_segments(strokes)
    assert len(segs) >= 1
    assert segs[0].direction == Direction.UP
    assert segs[0].end_bi == 4


def test_normalize_feat_bars_merge_contained_down_bars() -> None:
    """向上线段：两根被包含的向下特征合并为一根（高高、低高）。"""
    a = _FeatBar(low=100.0, high=110.0, stroke_idx=1)
    b = _FeatBar(low=102.0, high=108.0, stroke_idx=3)
    out = _normalize_feat_bars_include([a, b], Direction.UP)
    assert len(out) == 1
    assert out[0].high == 110.0
    assert out[0].low == 102.0
    assert out[0].stroke_idx == 3


def test_resolve_top_case2_uses_second_feature_sequence_fractal() -> None:
    """第一顶分型一二元素有缺口时，以第二特征序列中的顶分型中间元为准。"""
    a = _FeatBar(10.0, 14.0, 0)
    b = _FeatBar(15.0, 25.0, 2)
    c = _FeatBar(11.0, 14.0, 4)
    x = _FeatBar(10.0, 13.0, 6)
    y = _FeatBar(12.0, 22.0, 8)
    z = _FeatBar(11.0, 14.0, 10)
    norm = [a, b, c, x, y, z]
    mid = _resolve_feature_top_segment_end(norm)
    assert mid is not None
    assert mid.stroke_idx == 8


def test_legacy_segment_engine_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.segment_engine", "legacy", raising=False)
    strokes = [
        _stroke(0, Direction.UP, 100.0, 110.0),
        _stroke(1, Direction.DOWN, 110.0, 105.0),
        _stroke(2, Direction.UP, 105.0, 112.0),
        _stroke(3, Direction.DOWN, 112.0, 108.0),
        _stroke(4, Direction.UP, 108.0, 115.0),
    ]
    segs = build_segments(strokes)
    assert len(segs) >= 1
