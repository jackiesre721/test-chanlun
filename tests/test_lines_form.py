"""lines_form 形态粗分类。"""

import pytest

from app.core.models import Direction, Pivot, Stroke
from app.services.lines_form import analyze_lines_form


def _stroke(sp: float, ep: float, d: Direction) -> Stroke:
    return Stroke(
        start_idx=0,
        end_idx=0,
        norm_start_idx=0,
        norm_end_idx=0,
        start_price=sp,
        end_price=ep,
        direction=d,
    )


def test_lines_form_insufficient() -> None:
    s = analyze_lines_form([_stroke(1, 2, Direction.UP), _stroke(2, 1, Direction.DOWN)], [])
    assert s.primary == "insufficient"


def test_lines_form_stacked_bi_trend_hint() -> None:
    strokes = [
        _stroke(100, 90, Direction.DOWN),
        _stroke(90, 95, Direction.UP),
        _stroke(95, 88, Direction.DOWN),
        _stroke(88, 92, Direction.UP),
        _stroke(92, 85, Direction.DOWN),
        _stroke(85, 90, Direction.UP),
    ]
    p1 = Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=1, zd=80.0, zg=85.0, level="bi")
    p2 = Pivot(start_bi=3, end_bi=5, start_idx=2, end_idx=3, zd=90.0, zg=95.0, level="bi")
    out = analyze_lines_form(strokes, [p1, p2])
    assert out.primary == "trend"
    assert out.abc_hint is not None


def test_macd_extrema_shrink_filters_divergence(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.models import Direction, MacdPoint, Pivot, Stroke
    from app.services.chan_engine import build_divergences

    strokes = [
        Stroke(start_idx=0, end_idx=5, start_price=100, end_price=80, direction=Direction.DOWN),
        Stroke(start_idx=5, end_idx=10, start_price=80, end_price=95, direction=Direction.UP),
        Stroke(start_idx=10, end_idx=15, start_price=95, end_price=85, direction=Direction.DOWN),
        Stroke(start_idx=15, end_idx=20, start_price=85, end_price=93, direction=Direction.UP),
        Stroke(start_idx=20, end_idx=25, start_price=93, end_price=75, direction=Direction.DOWN),
    ]
    pivot = Pivot(start_bi=0, end_bi=2, start_idx=0, end_idx=15, zd=85, zg=95, level="bi", leave_seg_idx=4)
    macd = [MacdPoint(dif=1.0, dea=0, hist=10.0) for _ in range(30)]
    for i in range(20, 26):
        macd[i] = MacdPoint(dif=2.0, dea=0, hist=8.0)

    monkeypatch.setattr("app.core.config.settings.divergence_require_macd_extrema_shrink", True, raising=False)
    monkeypatch.setattr("app.core.config.settings.divergence_macd_extrema_max_ratio", 0.5, raising=False)

    assert build_divergences(strokes, [pivot], macd) == []
