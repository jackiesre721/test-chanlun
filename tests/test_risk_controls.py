import pytest

from app.core.models import (
    Fractal,
    MacdPoint,
    Pivot,
    PointType,
    PositionSizingRequest,
    Signal,
    SignalSide,
    TrailingStopRequest,
)
from app.services.chan_engine import _pivot_macd_pulls_near_zero_axis
from app.services.indicators import atr_last_wilder
from app.services.risk_controls import (
    compute_position_size,
    compute_trailing_stop,
    enrich_signals_with_sl_tp,
)


def test_position_size_linear_risk_model() -> None:
    out = compute_position_size(
        PositionSizingRequest(
            equity_usdt=10_000.0,
            risk_fraction=0.01,
            entry_price=100.0,
            stop_price=90.0,
        )
    )
    assert abs(out.risk_usdt - 100.0) < 1e-6
    assert abs(out.suggested_quantity - 10.0) < 1e-6
    assert abs(out.notional_usdt - 1_000.0) < 1e-6


def test_atr_last_wilder_positive() -> None:
    highs = [10.0 + i * 0.05 for i in range(40)]
    lows = [9.0 + i * 0.05 for i in range(40)]
    closes = [9.5 + i * 0.05 for i in range(40)]
    atr_val = atr_last_wilder(highs, lows, closes, period=14)
    assert atr_val > 0


def test_trailing_stop_long_uses_peak() -> None:
    from app.core.models import CompactOHLC

    tail = [CompactOHLC(high=110.0, low=100.0, close=105.0) for _ in range(20)]
    out = compute_trailing_stop(
        TrailingStopRequest(
            direction="LONG",
            entry_price=100.0,
            peak_price=120.0,
            atr_period=5,
            atr_multiplier=2.0,
            ohlc_tail=tail,
        )
    )
    assert out.stop_price < 120.0
    assert out.atr > 0


def test_pivot_macd_pulls_near_zero_axis_detects_small_dif() -> None:
    pts = [
        MacdPoint(dif=0.5, dea=0.0, hist=1.0),
        MacdPoint(dif=0.01, dea=0.0, hist=0.5),
        MacdPoint(dif=-0.4, dea=0.0, hist=-0.2),
    ]
    pivot = Pivot(start_bi=0, end_bi=0, start_idx=0, end_idx=2, zg=1.0, zd=0.5, level="bi")
    assert _pivot_macd_pulls_near_zero_axis(pivot, pts, abs_eps=0.02) is True


def _make_signal(side: SignalSide, idx: int, price: float, kind: str = "first") -> Signal:
    return Signal(
        idx=idx,
        side=side,
        kind=kind,
        time="2025-01-01",
        price=price,
        description="test",
        strength=0.5,
    )


def _make_fractal(f_type: PointType, norm_idx: int, price: float) -> Fractal:
    return Fractal(idx=norm_idx, type=f_type, norm_idx=norm_idx, price=price, time="2025-01-01")


def _make_pivot(zd: float, zg: float) -> Pivot:
    return Pivot(start_bi=0, end_bi=0, start_idx=0, end_idx=5, zg=zg, zd=zd, level="bi")


def test_position_size_with_leverage() -> None:
    out = compute_position_size(
        PositionSizingRequest(
            equity_usdt=10_000.0,
            risk_fraction=0.01,
            entry_price=100.0,
            stop_price=90.0,
            leverage=5,
        )
    )
    assert out.leverage == 5
    assert abs(out.risk_usdt - 100.0) < 1e-6
    assert abs(out.suggested_quantity - 10.0) < 1e-6
    assert abs(out.notional_usdt - 1_000.0) < 1e-6
    assert abs(out.required_margin - 200.0) < 1e-6
    assert out.liquidation_price is not None
    assert out.liquidation_price < 100.0
    assert abs(out.effective_risk_pct - 1.0) < 1e-6


def test_position_size_leverage_warnings() -> None:
    out = compute_position_size(
        PositionSizingRequest(
            equity_usdt=10_000.0,
            risk_fraction=0.02,
            entry_price=100.0,
            stop_price=90.0,
            leverage=10,
        )
    )
    assert any("风险比例" in w for w in out.warnings)
    assert any("10x" in w for w in out.warnings)


def test_enrich_signals_with_sl_tp_buy() -> None:
    sig = _make_signal(SignalSide.BUY, idx=50, price=100.0)
    # reversed order processes BOTTOM(35,92) first → stop_loss=92.0
    fractals = [
        _make_fractal(PointType.TOP, 30, 110.0),
        _make_fractal(PointType.BOTTOM, 40, 88.0),
        _make_fractal(PointType.BOTTOM, 35, 92.0),
    ]
    pivots = [_make_pivot(80.0, 105.0)]
    enriched = enrich_signals_with_sl_tp([sig], fractals, pivots)
    assert len(enriched) == 1
    s = enriched[0]
    assert s.stop_loss == 92.0
    assert s.take_profit is not None
    assert s.take_profit > 100.0
    assert s.risk_reward_ratio is not None
    assert s.risk_reward_ratio >= 2.0


def test_enrich_signals_with_sl_tp_sell() -> None:
    sig = _make_signal(SignalSide.SELL, idx=50, price=100.0, kind="first")
    # reversed order processes TOP(35,108) first → stop_loss=108.0
    fractals = [
        _make_fractal(PointType.BOTTOM, 40, 88.0),
        _make_fractal(PointType.TOP, 45, 115.0),
        _make_fractal(PointType.TOP, 35, 108.0),
    ]
    pivots = [_make_pivot(80.0, 120.0)]
    enriched = enrich_signals_with_sl_tp([sig], fractals, pivots)
    s = enriched[0]
    assert s.stop_loss == 108.0
    assert s.take_profit is not None
    assert s.take_profit < 100.0
    assert s.risk_reward_ratio is not None
    assert s.risk_reward_ratio >= 2.0


def test_enrich_signals_no_fractal_fallback_to_pivot() -> None:
    sig = _make_signal(SignalSide.BUY, idx=50, price=100.0)
    pivots = [_make_pivot(90.0, 110.0)]
    enriched = enrich_signals_with_sl_tp([sig], [], pivots)
    s = enriched[0]
    assert s.stop_loss == 90.0


def test_enrich_signals_no_fractal_no_pivot() -> None:
    sig = _make_signal(SignalSide.BUY, idx=50, price=100.0)
    enriched = enrich_signals_with_sl_tp([sig], [], [])
    s = enriched[0]
    assert s.stop_loss is None
    assert s.take_profit is None
    assert s.risk_reward_ratio is None


def test_enrich_signals_empty_list() -> None:
    assert enrich_signals_with_sl_tp([], [], []) == []
