"""Tests for EventBroadcaster pub/sub."""

import asyncio

from app.services.event_bus import EventBroadcaster


class TestSubscribe:
    def test_subscribe_returns_queue(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        assert bus.subscriber_count == 1

    def test_multiple_subscribers(self):
        bus = EventBroadcaster()
        bus.subscribe()
        bus.subscribe()
        assert bus.subscriber_count == 2

    def test_unsubscribe(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        bus.unsubscribe(q)
        assert bus.subscriber_count == 0

    def test_unsubscribe_missing_queue(self):
        bus = EventBroadcaster()
        q = asyncio.Queue()
        bus.unsubscribe(q)  # No error
        assert bus.subscriber_count == 0


class TestPublish:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_publish_reaches_subscriber(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        self._run(bus.publish("test", {"value": 42}))
        msg = q.get_nowait()
        assert msg["type"] == "test"
        assert msg["value"] == 42

    def test_publish_fan_out(self):
        bus = EventBroadcaster()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        self._run(bus.publish("tick", {"symbol": "BTCUSDT", "price": 100.0}))
        assert q1.get_nowait()["price"] == 100.0
        assert q2.get_nowait()["price"] == 100.0

    def test_publish_price_tick(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        self._run(bus.publish_price_tick("ETHUSDT", 2500.0))
        msg = q.get_nowait()
        assert msg["type"] == "price_tick"
        assert msg["symbol"] == "ETHUSDT"
        assert msg["price"] == 2500.0

    def test_publish_position_update(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        self._run(bus.publish_position_update([{"id": "p1"}], {"equity": 1100.0}))
        msg = q.get_nowait()
        assert msg["type"] == "position_update"
        assert msg["positions"][0]["id"] == "p1"
        assert msg["account"]["equity"] == 1100.0

    def test_publish_trade_closed(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        self._run(bus.publish_trade_closed({"id": "p1"}, "stop_loss"))
        msg = q.get_nowait()
        assert msg["type"] == "trade_closed"
        assert msg["reason"] == "stop_loss"

    def test_publish_trade_reduced(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        self._run(bus.publish_trade_reduced({"id": "p1"}, 0.25, 110.0, 5.0))
        msg = q.get_nowait()
        assert msg["type"] == "trade_reduced"
        assert msg["fraction"] == 0.25

    def test_publish_signal_detected(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        self._run(bus.publish_signal_detected("BTCUSDT", {"kind": "first"}))
        msg = q.get_nowait()
        assert msg["type"] == "signal_detected"
        assert msg["symbol"] == "BTCUSDT"

    def test_slow_subscriber_dropped(self):
        bus = EventBroadcaster()
        q = bus.subscribe()
        # Fill the queue to capacity
        async def fill():
            for i in range(512):
                await bus.publish("fill", {"i": i})
            await bus.publish("overflow", {"i": 999})
        asyncio.run(fill())
        assert bus.subscriber_count == 0
