"""Binance WebSocket kline listener — real-time upsert to PostgreSQL."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

import websockets

from app.core.config import settings
from app.services import symbol_registry
from app.db.engine import session_factory
from app.db.kline_store import prune_old_klines, upsert_klines
from app.repositories.market_data import BINANCE_INTERVALS

log = logging.getLogger(__name__)

_RECONNECT_INTERVAL = 23 * 3600  # 23h — reconnect before 24h forced close


def _build_stream_url() -> str:
    streams = []
    for symbol in symbol_registry.get_symbols():
        for bi in BINANCE_INTERVALS.values():
            streams.append(f"{symbol.lower()}@kline_{bi}")
    return f"{settings.binance_ws_url}/stream?streams={'/'.join(streams)}"


async def start_ws_listener() -> None:
    """Persistent WebSocket listener with auto-reconnect. Runs forever."""
    url = _build_stream_url()
    log.info("WS listener starting, %d streams", len(symbol_registry.get_symbols()) * len(BINANCE_INTERVALS))

    while True:
        connected_at = time.monotonic()
        try:
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=60,
                close_timeout=5,
            ) as ws:
                log.info("WS connected: %s", url[:80])
                async for raw in ws:
                    await _handle_message(raw)

                    if time.monotonic() - connected_at > _RECONNECT_INTERVAL:
                        log.info("WS reconnecting (23h rotation)")
                        await ws.close()
                        break

        except websockets.ConnectionClosed:
            log.warning("WS connection closed, reconnecting in %.1fs", settings.ws_reconnect_delay_seconds)
        except Exception:
            log.exception("WS error, reconnecting in %.1fs", settings.ws_reconnect_delay_seconds)

        await asyncio.sleep(settings.ws_reconnect_delay_seconds)


async def _handle_message(raw: "str | bytes") -> None:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return

    # Combined stream wraps payload in {"stream":..., "data":...}
    data = msg.get("data", msg)
    if data.get("e") != "kline":
        return

    k = data.get("k", {})
    symbol = k.get("s")
    interval = k.get("i")
    is_closed = k.get("x", False)

    if not symbol or not interval:
        return

    factory = session_factory()
    if factory is None:
        return

    row = (
        int(k["t"]),
        float(k["o"]),
        float(k["h"]),
        float(k["l"]),
        float(k["c"]),
        float(k["v"]),
    )

    try:
        async with factory() as session:
            n = await upsert_klines(session, symbol, interval, [row])
            if is_closed and n:
                log.info("WS kline closed: %s/%s open_time=%d", symbol, interval, row[0])
    except Exception:
        log.warning("WS upsert failed: %s/%s", symbol, interval, exc_info=True)
