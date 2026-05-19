"""Binance USD-M futures symbol whitelist."""

from __future__ import annotations

import logging

from app.repositories.market_data import BinanceRepository

log = logging.getLogger(__name__)

# Fixed whitelist — all USD-M futures.
_ALLOWED = frozenset({"SOLUSDT"})


async def refresh_symbols(repository: BinanceRepository) -> None:
    log.info("Symbol registry: using fixed whitelist of %d futures pairs", len(_ALLOWED))


def get_symbols() -> set[str]:
    return set(_ALLOWED)


def is_registry_degraded() -> bool:
    return False


def is_supported(symbol: str) -> bool:
    return symbol in _ALLOWED
