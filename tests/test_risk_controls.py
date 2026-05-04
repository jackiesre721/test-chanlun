from app.core.models import MacdPoint, Pivot, PositionSizingRequest, TrailingStopRequest
from app.services.chan_engine import _pivot_macd_pulls_near_zero_axis
from app.services.indicators import atr_last_wilder
from app.services.risk_controls import compute_position_size, compute_trailing_stop


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
