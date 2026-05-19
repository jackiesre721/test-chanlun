"""Tests for strategy optimizer: parameter generation, scoring, approval workflow."""

import pytest

from app.core.config import settings
from app.services.strategy_optimizer import (
    SEARCH_SPACE,
    StrategyOptimizer,
    OptimizationRun,
    _generate_param_combos,
    _override_settings,
    _score_backtest,
)
from app.core.models import QuickBacktestMetrics, QuickBacktestResponse


class TestParamGeneration:
    def test_generates_combos(self):
        combos = _generate_param_combos(SEARCH_SPACE)
        assert len(combos) > 0
        for c in combos:
            for key in SEARCH_SPACE:
                assert key in c
                assert c[key] in SEARCH_SPACE[key]

    def test_combo_count(self):
        expected = 1
        for v in SEARCH_SPACE.values():
            expected *= len(v)
        combos = _generate_param_combos(SEARCH_SPACE)
        assert len(combos) == expected


class TestOverrideSettings:
    def test_override_and_restore(self):
        original = settings.divergence_ratio
        with _override_settings({"divergence_ratio": 0.5}):
            assert settings.divergence_ratio == 0.5
        assert settings.divergence_ratio == original

    def test_multiple_overrides(self):
        orig_ratio = settings.divergence_ratio
        orig_engine = settings.segment_engine
        with _override_settings({"divergence_ratio": 0.6, "segment_engine": "strict67"}):
            assert settings.divergence_ratio == 0.6
            assert settings.segment_engine == "strict67"
        assert settings.divergence_ratio == orig_ratio
        assert settings.segment_engine == orig_engine


class TestScoring:
    def test_score_good_result(self):
        resp = QuickBacktestResponse(
            metrics=QuickBacktestMetrics(
                bars_used=1000, trades=20, final_equity_usdt=1200,
                total_return_fraction=0.2, max_drawdown_fraction=0.05,
                sharpe_naive=1.5, closed_trade_count=20,
                win_rate=0.7, profit_factor=2.0,
            ),
            trade_log=[], closed_trades=[], stats_by_signal_kind={},
        )
        score = _score_backtest(resp)
        assert score > 0

    def test_score_losing_result(self):
        resp = QuickBacktestResponse(
            metrics=QuickBacktestMetrics(
                bars_used=1000, trades=20, final_equity_usdt=800,
                total_return_fraction=-0.2, max_drawdown_fraction=0.3,
                sharpe_naive=-1.0, closed_trade_count=20,
                win_rate=0.3, profit_factor=0.5,
            ),
            trade_log=[], closed_trades=[], stats_by_signal_kind={},
        )
        score = _score_backtest(resp)
        assert score < 0.5  # Bad result should have low score


class TestOptimizerWorkflow:
    def test_approve_reject(self):
        opt = StrategyOptimizer()
        run = OptimizationRun(
            run_id="test-1",
            params={"divergence_ratio": 0.6},
            scores={"BTCUSDT": 0.5},
            avg_score=0.5,
            status="pending_approval",
            created_at="2026-01-01T00:00:00Z",
        )
        opt._runs.append(run)

        # Reject first
        assert opt.reject("test-1") is True
        assert opt.get_pending() == []

        # Add another and approve
        run2 = OptimizationRun(
            run_id="test-2",
            params={"divergence_ratio": 0.7},
            scores={"BTCUSDT": 0.6},
            avg_score=0.6,
            status="pending_approval",
            created_at="2026-01-01T00:00:00Z",
        )
        opt._runs.append(run2)
        opt._current_best = run2

        assert opt.approve("test-2") is True
        assert run2.status == "approved"
        assert settings.divergence_ratio == 0.7  # Applied

    def test_get_all_runs_sorted(self):
        opt = StrategyOptimizer()
        opt._runs = [
            OptimizationRun("a", {}, {}, 0.3, "pending_approval", "t1"),
            OptimizationRun("b", {}, {}, 0.8, "pending_approval", "t2"),
            OptimizationRun("c", {}, {}, 0.5, "pending_approval", "t3"),
        ]
        runs = opt.get_all_runs()
        assert runs[0]["run_id"] == "b"  # Highest score first
