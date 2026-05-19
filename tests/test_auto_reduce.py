"""Tests for auto position reduction: reduce_position, _parse_reduce_thresholds."""

from app.core.models import Signal, SignalSide
from app.trading.paper_engine import PaperEngine
from app.services.trading_loop import _parse_reduce_thresholds


def _engine(tmp_path, monkeypatch):
    """Create a PaperEngine with a temp DB."""
    import pathlib
    db = tmp_path / "test_reduce.sqlite"
    monkeypatch.setattr("app.trading.paper_engine.settings.paper_orders_db_path", str(db))
    return PaperEngine(initial_equity=1000.0, leverage=5, risk_fraction=0.01, fee_rate=0.0005)


def _buy_signal(price: float = 100.0, sl: float = 98.0, tp1: float = 102.0, tp2: float = 104.0) -> Signal:
    return Signal(
        side=SignalSide.BUY, kind="first", idx=10, time="2026-01-01T00:00:00Z",
        price=price, description="test", strength=1.0,
        stop_loss=sl, take_profit_1=tp1, take_profit=tp2,
    )


class TestReducePositionPartialClose:
    """reduce_position partial close -- verify quantity reduced, P&L recorded."""

    def test_partial_reduce_long(self, tmp_path, monkeypatch):
        engine = _engine(tmp_path, monkeypatch)
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        assert pid is not None

        positions = engine.get_positions("open")
        original_qty = positions[0].quantity

        # Reduce 25% at a profit price of 103
        pnl = engine.reduce_position(pid, 0.25, 103.0)
        assert pnl > 0  # LONG, price went up

        # Position should now be partial_closed with reduced quantity
        positions = engine.get_positions("partial_closed")
        assert len(positions) == 1
        p = positions[0]
        assert p.quantity < original_qty
        expected_qty = original_qty * 0.75
        assert abs(p.quantity - expected_qty) < 1e-6
        assert p.realized_pnl > 0

    def test_partial_reduce_short(self, tmp_path, monkeypatch):
        engine = _engine(tmp_path, monkeypatch)
        sig = Signal(
            side=SignalSide.SELL, kind="second", idx=10, time="2026-01-01T00:00:00Z",
            price=100.0, description="test", strength=1.0,
            stop_loss=102.0, take_profit_1=98.0, take_profit=96.0,
        )
        pid = engine.open_position_from_signal(sig, "ETHUSDT")
        assert pid is not None

        original_qty = engine.get_positions("open")[0].quantity

        # Reduce 30% at a profit price of 97 (SHORT profits when price drops)
        pnl = engine.reduce_position(pid, 0.30, 97.0)
        assert pnl > 0

        positions = engine.get_positions("partial_closed")
        assert len(positions) == 1
        expected_qty = original_qty * 0.70
        assert abs(positions[0].quantity - expected_qty) < 1e-6


class TestReducePositionFullClose:
    """reduce_position full close when fraction would leave nothing."""

    def test_full_close_via_reduce(self, tmp_path, monkeypatch):
        engine = _engine(tmp_path, monkeypatch)
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")

        # Reduce 100% -- should fully close
        pnl = engine.reduce_position(pid, 1.0, 105.0)
        assert pnl > 0

        # Position should be fully closed
        open_pos = engine.get_positions("open")
        partial_pos = engine.get_positions("partial_closed")
        closed_pos = engine.get_positions("closed")
        assert len(open_pos) == 0
        assert len(partial_pos) == 0
        assert len(closed_pos) == 1
        assert closed_pos[0].close_reason == "auto_reduce_full"
        assert closed_pos[0].realized_pnl > 0

    def test_nearly_full_close_reduces_to_partial(self, tmp_path, monkeypatch):
        engine = _engine(tmp_path, monkeypatch)
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")

        # Reduce 99% -- remaining is small but nonzero
        pnl = engine.reduce_position(pid, 0.99, 101.0)
        assert pnl > 0

        # Should be partial_closed, not fully closed
        partial_pos = engine.get_positions("partial_closed")
        assert len(partial_pos) == 1
        assert partial_pos[0].quantity < 1.0  # Very small remaining


class TestReducePositionNonExistent:
    """Reduce on non-existent position returns 0."""

    def test_reduce_nonexistent_position(self, tmp_path, monkeypatch):
        engine = _engine(tmp_path, monkeypatch)
        pnl = engine.reduce_position("nonexistent-id", 0.25, 100.0)
        assert pnl == 0.0

    def test_reduce_closed_position(self, tmp_path, monkeypatch):
        engine = _engine(tmp_path, monkeypatch)
        sig = _buy_signal(price=100.0, sl=98.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        engine.close_position(pid, 101.0, "manual")

        # Already closed, should return 0
        pnl = engine.reduce_position(pid, 0.25, 102.0)
        assert pnl == 0.0


class TestParseReduceThresholds:
    """_parse_reduce_thresholds parsing."""

    def test_parse_standard(self):
        result = _parse_reduce_thresholds("1.5:0.25,2.0:0.25,3.0:0.25")
        assert result == [(1.5, 0.25), (2.0, 0.25), (3.0, 0.25)]

    def test_parse_unsorted_input(self):
        result = _parse_reduce_thresholds("3.0:0.25,1.5:0.5,2.0:0.25")
        assert result == [(1.5, 0.5), (2.0, 0.25), (3.0, 0.25)]

    def test_parse_empty_string(self):
        result = _parse_reduce_thresholds("")
        assert result == []

    def test_parse_single_pair(self):
        result = _parse_reduce_thresholds("2.0:0.50")
        assert result == [(2.0, 0.50)]

    def test_parse_skips_invalid_entries(self):
        result = _parse_reduce_thresholds("1.5:0.25,invalid,2.0:0.25")
        assert result == [(1.5, 0.25), (2.0, 0.25)]

    def test_parse_whitespace(self):
        result = _parse_reduce_thresholds(" 1.5 : 0.25 , 2.0 : 0.30 ")
        assert result == [(1.5, 0.25), (2.0, 0.30)]
