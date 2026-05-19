"""Tests for PaperEngine: open/close positions, SL/TP, partial close, equity tracking."""

import tempfile
from pathlib import Path

import pytest

from app.core.models import Signal, SignalSide
from app.trading.paper_engine import PaperEngine


@pytest.fixture
def engine(tmp_path, monkeypatch):
    db = tmp_path / "test_paper.sqlite"
    monkeypatch.setattr("app.trading.paper_engine.settings.paper_orders_db_path", str(db))
    return PaperEngine(initial_equity=1000.0, leverage=5, risk_fraction=0.01, fee_rate=0.0005)


def _buy_signal(price: float = 100.0, sl: float = 98.0, tp1: float = 102.0, tp2: float = 104.0) -> Signal:
    return Signal(
        side=SignalSide.BUY, kind="first", idx=10, time="2026-01-01T00:00:00Z",
        price=price, description="test", strength=1.0,
        stop_loss=sl, take_profit_1=tp1, take_profit=tp2,
    )


def _sell_signal(price: float = 100.0, sl: float = 102.0, tp1: float = 98.0, tp2: float = 96.0) -> Signal:
    return Signal(
        side=SignalSide.SELL, kind="second", idx=10, time="2026-01-01T00:00:00Z",
        price=price, description="test", strength=1.0,
        stop_loss=sl, take_profit_1=tp1, take_profit=tp2,
    )


class TestOpenPosition:
    def test_open_long_from_signal(self, engine):
        sig = _buy_signal()
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        assert pid is not None
        positions = engine.get_positions("open")
        assert len(positions) == 1
        p = positions[0]
        assert p.side == "LONG"
        assert p.symbol == "BTCUSDT"
        assert p.entry_price == 100.0
        assert p.stop_loss == 98.0

    def test_open_short_from_signal(self, engine):
        sig = _sell_signal()
        pid = engine.open_position_from_signal(sig, "ETHUSDT")
        assert pid is not None
        positions = engine.get_positions("open")
        assert len(positions) == 1
        assert positions[0].side == "SHORT"

    def test_reject_no_stop_loss(self, engine):
        sig = Signal(
            side=SignalSide.BUY, kind="first", idx=10, time="2026-01-01T00:00:00Z",
            price=100.0, description="test", strength=1.0,
        )
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        assert pid is None

    def test_reject_duplicate_symbol(self, engine):
        sig = _buy_signal()
        pid1 = engine.open_position_from_signal(sig, "BTCUSDT")
        assert pid1 is not None
        pid2 = engine.open_position_from_signal(sig, "BTCUSDT")
        assert pid2 is None

    def test_reject_max_positions(self, engine):
        engine.max_positions = 2
        for i, sym in enumerate(["BTCUSDT", "ETHUSDT", "SOLUSDT"]):
            sig = _buy_signal(price=100.0 + i)
            engine.open_position_from_signal(sig, sym)
        positions = engine.get_positions("open")
        assert len(positions) == 2

    def test_balance_deducted_on_open(self, engine):
        sig = _buy_signal(price=100.0, sl=99.0)
        engine.open_position_from_signal(sig, "BTCUSDT")
        summary = engine.get_account_summary()
        assert summary.available_balance < 1000.0


class TestSLTP:
    def test_stop_loss_triggered_long(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        closed = engine.check_sl_tp("BTCUSDT", high=99.0, low=97.0, close=97.5)
        assert pid in closed
        positions = engine.get_positions("closed")
        assert len(positions) == 1
        assert positions[0].close_reason == "stop_loss"

    def test_stop_loss_triggered_short(self, engine):
        sig = _sell_signal(price=100.0, sl=102.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        closed = engine.check_sl_tp("BTCUSDT", high=103.0, low=99.0, close=102.5)
        assert pid in closed
        assert engine.get_positions("closed")[0].close_reason == "stop_loss"

    def test_tp1_partial_close(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0, tp1=102.0, tp2=104.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        engine.check_sl_tp("BTCUSDT", high=103.0, low=100.0, close=102.5)
        positions = engine.get_positions()
        p = [x for x in positions if x.position_id == pid][0]
        assert p.status == "partial_closed"
        assert p.quantity < 5.0  # quantity reduced by tp1_ratio (50%)

    def test_no_trigger_when_range_safe(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0, tp1=105.0, tp2=110.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        closed = engine.check_sl_tp("BTCUSDT", high=101.0, low=99.0, close=100.5)
        assert len(closed) == 0


class TestClosePosition:
    def test_manual_close(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        pnl = engine.close_position(pid, 101.0, "manual")
        assert pnl > 0  # Price went up, LONG should be profitable

    def test_close_updates_equity(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        engine.close_position(pid, 101.0, "manual")
        summary = engine.get_account_summary()
        assert summary.total_realized_pnl > 0


class TestAccountSummary:
    def test_initial_summary(self, engine):
        summary = engine.get_account_summary()
        assert summary.initial_equity == 1000.0
        assert summary.current_equity == 1000.0
        assert summary.open_positions == 0

    def test_summary_with_open_position(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0)
        engine.open_position_from_signal(sig, "BTCUSDT")
        summary = engine.get_account_summary()
        assert summary.open_positions == 1
        assert summary.available_balance < 1000.0


class TestTrailingStop:
    def test_trailing_stop_updates(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        engine.update_trailing_stop(pid, 99.5)
        positions = engine.get_positions("open")
        assert positions[0].stop_loss >= 99.5
