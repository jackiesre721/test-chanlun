"""Tests for daily report builder."""

import tempfile
from pathlib import Path

import pytest

from app.services.daily_report import build_daily_report, _sparkline
from app.core.models import Signal, SignalSide
from app.trading.paper_engine import PaperEngine


@pytest.fixture
def engine(tmp_path, monkeypatch):
    db = tmp_path / "test_report.sqlite"
    monkeypatch.setattr("app.trading.paper_engine.settings.paper_orders_db_path", str(db))
    return PaperEngine(initial_equity=1000.0, leverage=5, risk_fraction=0.01)


def _buy_signal(price=100.0, sl=98.0, tp=104.0):
    return Signal(
        side=SignalSide.BUY, kind="first", idx=10, time="2026-01-01T00:00:00Z",
        price=price, description="test", strength=1.0,
        stop_loss=sl, take_profit=tp,
    )


class TestDailyReport:
    def test_empty_report(self, engine):
        report = build_daily_report(engine)
        assert "elements" in report
        assert report["header"]["title"]["content"].startswith("交易日报")

    def test_report_with_position(self, engine):
        sig = _buy_signal()
        engine.open_position_from_signal(sig, "BTCUSDT")
        report = build_daily_report(engine)
        elements_text = str(report["elements"])
        assert "BTCUSDT" in elements_text
        assert "LONG" in elements_text

    def test_report_after_close(self, engine):
        sig = _buy_signal(price=100.0, sl=98.0, tp=104.0)
        pid = engine.open_position_from_signal(sig, "BTCUSDT")
        engine.close_position(pid, 102.0, "manual")
        report = build_daily_report(engine)
        elements_text = str(report["elements"])
        assert "今日成交" in elements_text
        assert "BTCUSDT" in elements_text

    def test_header_color_changes_with_pnl(self, engine):
        report = build_daily_report(engine)
        assert report["header"]["template"] == "blue"  # No loss, default blue


class TestSparkline:
    def test_basic_sparkline(self):
        result = _sparkline([1, 2, 3, 4, 5])
        assert len(result) == 5
        assert all(c in "▁▂▃▄▅▆▇█" for c in result)

    def test_empty_values(self):
        assert _sparkline([]) == ""
        assert _sparkline([1]) == ""

    def test_flat_values(self):
        result = _sparkline([5, 5, 5, 5])
        assert len(result) == 4
        assert all(c == "▅" for c in result)
