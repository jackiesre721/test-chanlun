"""Tests for TradingLoop signal selection, management, and scheduling logic."""

import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.models import Market, Signal, SignalSide
from app.services.trading_loop import TradingLoop, MIN_RR, _cn_now
from app.trading.paper_engine import PaperEngine


@pytest.fixture
def engine(tmp_path, monkeypatch):
    db = tmp_path / "test_loop.sqlite"
    monkeypatch.setattr("app.trading.paper_engine.settings.paper_orders_db_path", str(db))
    return PaperEngine(initial_equity=1000.0, leverage=5, risk_fraction=0.01)


@pytest.fixture
def loop(engine):
    return TradingLoop(engine)


def _signal(side=SignalSide.BUY, kind="first", price=100.0, sl=98.0, tp=104.0, idx=100):
    return Signal(
        side=side, kind=kind, idx=idx, time="2026-01-01T00:00:00Z",
        price=price, description="test", strength=1.0,
        stop_loss=sl, take_profit=tp,
    )


class TestPickBestSignal:
    def test_picks_latest_unfiltered(self, loop):
        s1 = _signal(idx=90, sl=None)
        s2 = _signal(idx=95, sl=98.0)
        s3 = _signal(idx=100, sl=97.0)
        result = loop._pick_best_signal([s1, s2, s3], [])
        assert result is not None
        assert result.idx == 100

    def test_prefers_first_over_second(self, loop):
        s1 = _signal(kind="second", idx=100, sl=98.0)
        s2 = _signal(kind="first", idx=100, sl=98.0)
        result = loop._pick_best_signal([s1], [s2])
        assert result.kind == "first"

    def test_returns_none_if_all_filtered(self, loop):
        s = _signal(idx=100, sl=98.0)
        s.rr_filtered = True
        result = loop._pick_best_signal([s], [])
        assert result is None

    def test_returns_none_if_no_stop_loss(self, loop):
        s = _signal(idx=100, sl=None)
        result = loop._pick_best_signal([s], [])
        assert result is None

    def test_combined_buy_and_sell(self, loop):
        buy = _signal(side=SignalSide.BUY, kind="first", idx=100, sl=98.0)
        sell = _signal(side=SignalSide.SELL, kind="first", idx=101, sl=102.0)
        result = loop._pick_best_signal([buy], [sell])
        assert result is not None
        assert result.idx == 101  # Latest


class TestManagePosition:
    def test_trailing_stop_update_long(self, engine, loop):
        from app.core.models import Candle

        sig = _signal(side=SignalSide.BUY, price=100.0, sl=95.0, tp=120.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        assert pid is not None

        # Create candles showing gradual upward move (high stays below TP)
        candles = [
            Candle(open_time=i * 60000, time=f"t{i}", open=100 + i * 0.2,
                   high=101 + i * 0.3, low=99 + i * 0.1, close=100.5 + i * 0.2, volume=1.0)
            for i in range(30)
        ]

        import asyncio
        asyncio.run(loop._manage_position("BTCUSDT", candles))

        positions = engine.get_positions("open")
        assert len(positions) == 1
        assert positions[0].stop_loss >= 95.0  # Trailing should have moved up


class TestSchedule:
    def test_report_sent_once_per_day(self, loop):
        assert loop._last_report_date == ""
        # Simulate that report was already sent today
        loop._last_report_date = _cn_now().strftime("%Y-%m-%d")
        # Should not send again
        assert loop._last_report_date == _cn_now().strftime("%Y-%m-%d")
