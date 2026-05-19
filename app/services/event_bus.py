"""AsyncIO pub/sub event bus for broadcasting trading events to WebSocket clients."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)


class EventBroadcaster:
    """Fan-out pub/sub: backend services publish, all WS subscriber queues receive."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        msg = {"type": event_type, **data}
        dead: list[asyncio.Queue[dict[str, Any]]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            log.warning("Dropping slow subscriber, removing queue")
            self.unsubscribe(q)

    async def publish_price_tick(self, symbol: str, price: float) -> None:
        await self.publish("price_tick", {"symbol": symbol, "price": price})

    async def publish_position_update(
        self, positions: list[dict[str, Any]], account: dict[str, Any]
    ) -> None:
        await self.publish("position_update", {"positions": positions, "account": account})

    async def publish_trade_closed(self, position: dict[str, Any], reason: str) -> None:
        await self.publish("trade_closed", {"position": position, "reason": reason})

    async def publish_trade_reduced(
        self, position: dict[str, Any], fraction: float, price: float, pnl: float
    ) -> None:
        await self.publish(
            "trade_reduced",
            {"position": position, "fraction": fraction, "price": price, "pnl": pnl},
        )

    async def publish_signal_detected(self, symbol: str, signal: dict[str, Any]) -> None:
        await self.publish("signal_detected", {"symbol": symbol, "signal": signal})

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
