"""Binance USDT trading pair whitelist with TTL-based in-memory cache."""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.repositories.market_data import BinanceRepository

log = logging.getLogger(__name__)

_FALLBACK = {"BTCUSDT", "ETHUSDT"}
_symbols: set[str] = set(_FALLBACK)
_expires_at: float = 0.0
_TTL = 3600  # 1 hour
# True when the last Binance registry refresh failed or returned empty (still serving fallback/cache).
_registry_degraded: bool = True


async def refresh_symbols(repository: BinanceRepository) -> None:
    global _symbols, _expires_at, _registry_degraded
    if time.monotonic() < _expires_at:
        return
    try:
        fetched = await repository.get_symbols()
        if fetched:
            _symbols = set(fetched)
            _expires_at = time.monotonic() + _TTL
            _registry_degraded = False
            log.info("Symbol registry refreshed: %d USDT pairs", len(_symbols))
        else:
            log.warning("get_symbols() returned empty, keeping %d existing symbols", len(_symbols))
            _registry_degraded = True
    except Exception:
        log.warning("Failed to refresh symbol registry, keeping %d existing symbols", len(_symbols), exc_info=True)
        _registry_degraded = True


def get_symbols() -> set[str]:
    return set(_symbols)


def is_registry_degraded() -> bool:
    """前台可提示：列表可能仅为内置兜底或未更新的缓存。"""
    return _registry_degraded


def is_supported(symbol: str) -> bool:
    return symbol in _symbols
