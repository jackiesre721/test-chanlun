"""Strategy parameter optimizer: grid search + backtest evaluation with cross-symbol validation."""

from __future__ import annotations

import itertools
import json
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from app.core.config import settings
from app.core.models import Market, QuickBacktestRequest, QuickBacktestResponse
from app.repositories.market_data import BinanceRepository
from app.services.backtest_quick import run_quick_backtest

log = logging.getLogger(__name__)

# Parameter search space
SEARCH_SPACE: dict[str, list[Any]] = {
    "divergence_ratio": [0.6, 0.7, 0.8, 0.9],
    "divergence_macd_metric": ["area", "hump", "either"],
    "segment_engine": ["legacy", "strict67"],
    "stroke_collapse_shallow_reversal": [True, False],
    "bsp1_only_multibi_zs": [True, False],
    "enable_t1p_pan_first_signals": [True, False],
}

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSDT", "DOGEUSDT"]

# Scoring weights
_W_SHARPE = 0.4
_W_WINRATE = 0.2
_W_PF = 0.2
_W_DD = 0.2


@dataclass
class OptimizationRun:
    run_id: str
    params: dict[str, Any]
    scores: dict[str, float]
    avg_score: float
    status: str  # pending_approval, approved, rejected
    created_at: str
    approved_at: str | None = None


@contextmanager
def _override_settings(overrides: dict[str, Any]):
    """Temporarily override settings values."""
    saved = {}
    for key, val in overrides.items():
        saved[key] = getattr(settings, key)
        setattr(settings, key, val)
    try:
        yield
    finally:
        for key, val in saved.items():
            setattr(settings, key, val)


def _score_backtest(resp: QuickBacktestResponse) -> float:
    m = resp.metrics
    sharpe = m.sharpe_naive or 0
    win_rate = m.win_rate or 0
    pf = m.profit_factor or 0
    dd = m.max_drawdown_fraction or 0

    # Normalize sharpe to 0-1 range (clip at 3)
    sharpe_n = min(max(sharpe, 0) / 3.0, 1.0)
    # Normalize pf to 0-1 (clip at 3)
    pf_n = min(max(pf, 0) / 3.0, 1.0)
    # dd is already 0-1, penalize
    dd_n = min(dd, 1.0)

    return sharpe_n * _W_SHARPE + win_rate * _W_WINRATE + pf_n * _W_PF - dd_n * _W_DD


async def _evaluate_params(
    repository: BinanceRepository,
    params: dict[str, Any],
    symbols: list[str],
    interval: str = "15",
) -> dict[str, float]:
    """Run backtest with given params across all symbols, return per-symbol scores."""
    scores: dict[str, float] = {}
    with _override_settings(params):
        for symbol in symbols:
            try:
                req = QuickBacktestRequest(
                    market=Market.CRYPTO,
                    symbol=symbol,
                    interval=interval,
                    strategy="long_short",
                    initial_equity_usdt=1000.0,
                    leverage=5,
                    fee_bps=10,
                )
                resp = await run_quick_backtest(repository, req)
                scores[symbol] = _score_backtest(resp)
            except Exception as e:
                log.warning("Optimization backtest failed for %s: %s", symbol, e)
                scores[symbol] = 0.0
    return scores


def _generate_param_combos(space: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(space.keys())
    values = list(space.values())
    combos = []
    for combo in itertools.product(*values):
        combos.append(dict(zip(keys, combo)))
    return combos


class StrategyOptimizer:
    """Manages optimization runs with approval workflow."""

    def __init__(self):
        self._runs: list[OptimizationRun] = []
        self._current_best: OptimizationRun | None = None

    async def run_optimization(
        self,
        repository: BinanceRepository,
        max_combos: int = 50,
    ) -> OptimizationRun | None:
        """Run grid search optimization. Returns best run for approval."""
        combos = _generate_param_combos(SEARCH_SPACE)
        log.info("Optimization: %d parameter combinations to evaluate", len(combos))

        # Limit combos for practical runtime
        if len(combos) > max_combos:
            import random
            random.seed(42)
            combos = random.sample(combos, max_combos)

        best_run: OptimizationRun | None = None
        for i, params in enumerate(combos):
            scores = await _evaluate_params(repository, params, SYMBOLS)
            avg = sum(scores.values()) / len(scores) if scores else 0

            run = OptimizationRun(
                run_id=str(uuid.uuid4()),
                params=params,
                scores=scores,
                avg_score=avg,
                status="pending_approval",
                created_at=datetime.now(tz=timezone.utc).isoformat(),
            )
            self._runs.append(run)

            if best_run is None or avg > best_run.avg_score:
                best_run = run

            if (i + 1) % 10 == 0:
                log.info("Optimization progress: %d/%d, best avg=%.4f", i + 1, len(combos), best_run.avg_score if best_run else 0)

        if best_run:
            self._current_best = best_run
            log.info("Optimization complete. Best params: %s, avg_score=%.4f", best_run.params, best_run.avg_score)

        return best_run

    def get_pending(self) -> list[OptimizationRun]:
        return [r for r in self._runs if r.status == "pending_approval"]

    def get_best(self) -> OptimizationRun | None:
        return self._current_best

    def approve(self, run_id: str) -> bool:
        for r in self._runs:
            if r.run_id == run_id and r.status == "pending_approval":
                r.status = "approved"
                r.approved_at = datetime.now(tz=timezone.utc).isoformat()
                # Apply params
                for key, val in r.params.items():
                    setattr(settings, key, val)
                log.info("Approved and applied params: %s", r.params)
                return True
        return False

    def reject(self, run_id: str) -> bool:
        for r in self._runs:
            if r.run_id == run_id and r.status == "pending_approval":
                r.status = "rejected"
                return True
        return False

    def get_all_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        sorted_runs = sorted(self._runs, key=lambda r: r.avg_score, reverse=True)[:limit]
        return [
            {
                "run_id": r.run_id,
                "params": r.params,
                "avg_score": round(r.avg_score, 4),
                "scores": {k: round(v, 4) for k, v in r.scores.items()},
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in sorted_runs
        ]
