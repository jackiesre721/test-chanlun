"""Binance USD-M Futures bookTicker price feed via WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

from app.services.event_bus import EventBroadcaster

log = logging.getLogger(__name__)

_BINANCE_WS_URL = "wss://fstream.binance.com/stream"
_INITIAL_BACKOFF = 5.0
_MAX_BACKOFF = 60.0


class PriceFeedService:
    """Subscribe to Binance USD-M @bookTicker streams for real-time prices."""

    SYMBOLS = ["btcusdt", "ethusdt", "solusdt", "xauusdt", "dogeusdt"]

    def __init__(self, event_bus: EventBroadcaster) -> None:
        self._event_bus = event_bus
        self._prices: dict[str, float] = {}
        self._running = False

    @staticmethod
    def _build_stream_url(symbols: list[str]) -> str:
        streams = "/".join(f"{s}@bookTicker" for s in symbols)
        return f"{_BINANCE_WS_URL}?streams={streams}"

    async def start(self) -> None:
        """Connect to Binance combined stream and process bookTicker messages.

        Runs in a reconnect loop with exponential backoff until stop() is called.
        """
        self._running = True
        url = self._build_stream_url(self.SYMBOLS)
        backoff = _INITIAL_BACKOFF

        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    log.info("Connected to Binance price feed: %s", url)
                    backoff = _INITIAL_BACKOFF  # reset on successful connect

                    async for raw in ws:
                        if not self._running:
                            break
                        await self._handle_message(raw)

            except (
                websockets.ConnectionClosed,
                websockets.InvalidURI,
                websockets.InvalidHandshake,
                OSError,
            ) as exc:
                if not self._running:
                    break
                log.warning(
                    "Price feed disconnected (%s). Reconnecting in %.0fs",
                    exc,
                    backoff,
                )
                await self._sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF)

    async def _handle_message(self, raw: str | bytes) -> None:
        """Parse a combined-stream bookTicker message and update prices."""
        try:
            msg: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            log.warning("Skipping non-JSON message: %s", raw)
            return

        data = msg.get("data")
        if data is None:
            return

        stream: str = msg.get("stream", "")
        if not stream.endswith("@bookTicker"):
            return

        bid_str: str | None = data.get("b")
        ask_str: str | None = data.get("a")
        if bid_str is None or ask_str is None:
            return

        try:
            bid = float(bid_str)
            ask = float(ask_str)
        except (ValueError, TypeError):
            log.warning("Invalid bid/ask in message: %s", raw)
            return

        mid = (bid + ask) / 2
        symbol_lower = stream.split("@")[0]
        symbol = symbol_lower.upper()

        self._prices[symbol] = mid
        await self._event_bus.publish_price_tick(symbol, mid)

    async def _sleep(self, seconds: float) -> None:
        """Interruptible sleep that exits early when stop() is called."""
        try:
            await asyncio.wait_for(
                asyncio.sleep(seconds),
                timeout=seconds + 0.1,
            )
        except asyncio.CancelledError:
            pass

    def stop(self) -> None:
        """Signal the feed loop to stop."""
        self._running = False

    def get_price(self, symbol: str) -> float | None:
        """Return the latest mid-price for *symbol*, or None if unseen."""
        return self._prices.get(symbol.upper())

    def get_all_prices(self) -> dict[str, float]:
        """Return a shallow copy of all cached prices."""
        return dict(self._prices)
