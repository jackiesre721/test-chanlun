from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.core.config import settings
from app.services import symbol_registry
from app.db.engine import session_factory
from app.db.kline_store import latest_open_time, prune_old_klines, upsert_klines
from app.repositories.market_data import BINANCE_INTERVALS, _INTERVAL_MS

log = logging.getLogger(__name__)

_FETCH_CONCURRENCY = 3


async def sync_once() -> None:
    factory = session_factory()
    if factory is None:
        return

    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

    async def sync_pair(symbol: str, interval_code: str) -> None:
        async with semaphore:
            await _sync_one_pair(factory, symbol, interval_code)

    tasks = [
        sync_pair(symbol, interval_code)
        for symbol in symbol_registry.get_symbols()
        for interval_code in BINANCE_INTERVALS
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    try:
        async with factory() as session:
            deleted = await prune_old_klines(session, settings.sync_retention_days)
            if deleted:
                log.info("Pruned %d old klines beyond %d days", deleted, settings.sync_retention_days)
    except Exception:
        log.warning("Prune failed", exc_info=True)


async def _sync_one_pair(factory, symbol: str, interval_code: str) -> None:
    bi = BINANCE_INTERVALS[interval_code]
    width_ms = _INTERVAL_MS.get(interval_code, 60_000)

    try:
        async with factory() as session:
            last_time = await latest_open_time(session, symbol, bi)
    except Exception:
        log.warning("Failed to query latest_open_time for %s/%s", symbol, bi, exc_info=True)
        return

    now_ms = int(time.time() * 1000)
    if last_time is not None and now_ms - last_time < width_ms:
        return

    from app.repositories.market_data import BinanceRepository

    repo = BinanceRepository(pg_session_factory=None)

    if last_time is None:
        gap_ms = settings.sync_retention_days * 86_400_000
    else:
        gap_ms = now_ms - last_time

    gap_bars = min(int(gap_ms / width_ms) + 2, 1500)
    if gap_bars <= 0:
        return

    try:
        candles = await repo.get_klines(symbol, interval_code, gap_bars)
    except Exception:
        log.warning("Binance fetch failed for %s/%s", symbol, bi, exc_info=True)
        return

    if not candles:
        return

    rows = [(c.open_time, c.open, c.high, c.low, c.close, c.volume) for c in candles]
    try:
        async with factory() as session:
            n = await upsert_klines(session, symbol, bi, rows)
            if n:
                log.info("Synced %d new klines for %s/%s", n, symbol, bi)
    except Exception:
        log.warning("PG persist failed for %s/%s", symbol, bi, exc_info=True)


async def backfill(days: Optional[int] = None) -> None:
    factory = session_factory()
    if factory is None:
        log.error("database_url not configured, cannot backfill")
        return

    days = days or settings.sync_retention_days
    log.info("Starting backfill for %d days across %d symbols", days, len(symbol_registry.get_symbols()))

    from app.repositories.market_data import BinanceRepository

    repo = BinanceRepository(pg_session_factory=None)

    for symbol in symbol_registry.get_symbols():
        for interval_code, bi in BINANCE_INTERVALS.items():
            width_ms = _INTERVAL_MS.get(interval_code, 60_000)
            total_bars = int(days * 86_400_000 / width_ms)
            total_bars = min(total_bars, 50_000)

            log.info("Backfilling %s/%s: ~%d bars", symbol, bi, total_bars)

            try:
                candles = await repo.get_klines_history(symbol, interval_code, total_bars)
            except Exception:
                log.warning("Backfill fetch failed for %s/%s", symbol, bi, exc_info=True)
                continue

            if not candles:
                continue

            rows = [(c.open_time, c.open, c.high, c.low, c.close, c.volume) for c in candles]
            try:
                async with factory() as session:
                    n = await upsert_klines(session, symbol, bi, rows)
                    log.info("Backfilled %s/%s: %d/%d rows persisted", symbol, bi, n, len(rows))
            except Exception:
                log.warning("Backfill persist failed for %s/%s", symbol, bi, exc_info=True)

            await asyncio.sleep(0.1)

    log.info("Backfill complete")
