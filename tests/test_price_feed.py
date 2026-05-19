"""Tests for PriceFeedService — mocked WebSocket connection."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.event_bus import EventBroadcaster
from app.services.price_feed import PriceFeedService


def _run(coro):
    """Run a coroutine on a fresh event loop (no pytest-asyncio)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _book_ticker(symbol: str, bid: str, ask: str) -> str:
    """Build a combined-stream bookTicker JSON message."""
    return json.dumps({
        "stream": f"{symbol}@bookTicker",
        "data": {"b": bid, "a": ask},
    })


class TestGetPrice:
    def test_returns_none_for_unknown_symbol(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        assert feed.get_price("BTCUSDT") is None

    def test_returns_price_after_update(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(_book_ticker("btcusdt", "100.0", "102.0")))
        assert feed.get_price("BTCUSDT") == 101.0

    def test_case_insensitive_lookup(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(_book_ticker("btcusdt", "50.0", "52.0")))
        assert feed.get_price("btcusdt") == 51.0
        assert feed.get_price("BtcUsDt") == 51.0


class TestGetAllPrices:
    def test_empty_initially(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        assert feed.get_all_prices() == {}

    def test_returns_copy(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(_book_ticker("btcusdt", "100.0", "102.0")))
        prices = feed.get_all_prices()
        assert prices == {"BTCUSDT": 101.0}
        # Mutating the copy should not affect internal state
        prices["BTCUSDT"] = 999.0
        assert feed.get_price("BTCUSDT") == 101.0

    def test_multiple_symbols(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(_book_ticker("btcusdt", "100.0", "102.0")))
        _run(feed._handle_message(_book_ticker("ethusdt", "2000.0", "2002.0")))
        assert feed.get_all_prices() == {"BTCUSDT": 101.0, "ETHUSDT": 2001.0}


class TestPublishesToEventBus:
    def test_publishes_price_tick(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(_book_ticker("solusdt", "150.0", "152.0")))
        msg = q.get_nowait()
        assert msg["type"] == "price_tick"
        assert msg["symbol"] == "SOLUSDT"
        assert msg["price"] == 151.0

    def test_publishes_each_update(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(_book_ticker("btcusdt", "100.0", "102.0")))
        _run(feed._handle_message(_book_ticker("ethusdt", "2000.0", "2002.0")))
        msg1 = q.get_nowait()
        msg2 = q.get_nowait()
        assert msg1["symbol"] == "BTCUSDT"
        assert msg2["symbol"] == "ETHUSDT"


class TestHandleMessageEdgeCases:
    def test_skips_invalid_json(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message("not json"))
        assert feed.get_all_prices() == {}

    def test_skips_message_without_data(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(json.dumps({"stream": "btcusdt@bookTicker"})))
        assert feed.get_all_prices() == {}

    def test_skips_non_bookticker_stream(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(json.dumps({
            "stream": "btcusdt@trade",
            "data": {"b": "100.0", "a": "102.0"},
        })))
        assert feed.get_all_prices() == {}

    def test_skips_missing_bid(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(json.dumps({
            "stream": "btcusdt@bookTicker",
            "data": {"a": "102.0"},
        })))
        assert feed.get_all_prices() == {}

    def test_skips_non_numeric_bid(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        _run(feed._handle_message(json.dumps({
            "stream": "btcusdt@bookTicker",
            "data": {"b": "abc", "a": "102.0"},
        })))
        assert feed.get_all_prices() == {}


class TestStop:
    def test_stop_sets_running_false(self):
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)
        feed._running = True
        feed.stop()
        assert feed._running is False


class TestBuildStreamUrl:
    def test_two_symbols(self):
        url = PriceFeedService._build_stream_url(["btcusdt", "ethusdt"])
        assert url == "wss://fstream.binance.com/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker"

    def test_all_symbols(self):
        url = PriceFeedService._build_stream_url(PriceFeedService.SYMBOLS)
        assert "btcusdt@bookTicker" in url
        assert "ethusdt@bookTicker" in url
        assert "solusdt@bookTicker" in url
        assert "xauusdt@bookTicker" in url
        assert "dogeusdt@bookTicker" in url
        assert url.startswith("wss://fstream.binance.com/stream?streams=")


class TestStartIntegration:
    def test_processes_messages_from_websocket(self):
        """start() reads WS messages and publishes price ticks."""
        bus = EventBroadcaster()
        q = bus.subscribe()
        feed = PriceFeedService(bus)

        messages = [
            _book_ticker("btcusdt", "50000.0", "50002.0"),
            _book_ticker("ethusdt", "3000.0", "3002.0"),
        ]

        async def fake_ws_aiter():
            for m in messages:
                yield m
            feed.stop()

        class FakeWs:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            def __aiter__(self):
                return fake_ws_aiter()

        with patch("app.services.price_feed.websockets.connect", return_value=FakeWs()):
            _run(feed.start())

        msg1 = q.get_nowait()
        assert msg1["symbol"] == "BTCUSDT"
        assert msg1["price"] == 50001.0
        msg2 = q.get_nowait()
        assert msg2["symbol"] == "ETHUSDT"
        assert msg2["price"] == 3001.0

    def test_reconnect_with_backoff_on_disconnect(self):
        """On connection error, wait with exponential backoff then retry."""
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)

        connect_calls = 0

        class FakeConnect:
            def __init__(self, url):
                pass

            async def __aenter__(self):
                nonlocal connect_calls
                connect_calls += 1
                if connect_calls == 1:
                    raise OSError("connection lost")
                # Second connect succeeds; stop the service inside.
                feed.stop()
                return self

            async def __aexit__(self, *args):
                pass

            async def __aiter__(self):
                return
                yield  # make this an async generator

        with patch("app.services.price_feed.websockets.connect", side_effect=FakeConnect):
            with patch.object(feed, "_sleep", new_callable=AsyncMock) as mock_sleep:
                _run(feed.start())
                # First reconnect should use initial backoff of 5.0s
                mock_sleep.assert_any_call(5.0)

        assert connect_calls == 2

    def test_backoff_doubles_on_repeated_failures(self):
        """Backoff doubles on each failure up to the maximum."""
        bus = EventBroadcaster()
        feed = PriceFeedService(bus)

        connect_calls = 0

        class AlwaysFail:
            def __init__(self, url):
                pass

            async def __aenter__(self):
                nonlocal connect_calls
                connect_calls += 1
                if connect_calls >= 4:
                    feed.stop()
                raise OSError("fail")

            async def __aexit__(self, *args):
                pass

        with patch("app.services.price_feed.websockets.connect", side_effect=AlwaysFail):
            with patch.object(feed, "_sleep", new_callable=AsyncMock) as mock_sleep:
                _run(feed.start())
                call_args = [c.args[0] for c in mock_sleep.call_args_list]

        assert connect_calls >= 4
        # Backoff sequence: 5.0, 10.0, 20.0, ...
        assert call_args[0] == 5.0
        assert call_args[1] == 10.0
        assert call_args[2] == 20.0
