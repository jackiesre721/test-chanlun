"""WS-driven trading loop: price ticks → manage positions, periodic scan → signals.

Runs 24/7 with:
- Price tick driven position management (SL/TP, auto-reduce, trailing stop)
- Periodic signal scanning (every scan_seconds)
- Time-based daily report and optimization scheduling
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.config import settings
from app.core.models import Market, Signal, SignalSide
from app.repositories.market_data import BinanceRepository
from app.services.analysis_pipeline import build_analyze_bundle
from app.services.event_bus import EventBroadcaster
from app.services.indicators import atr_last_wilder
from app.services.price_feed import PriceFeedService
from app.services.risk_controls import enrich_signals_with_sl_tp
from app.trading.paper_engine import PaperEngine

log = logging.getLogger(__name__)

# Symbols to scan
SCAN_SYMBOLS = ["SOLUSDT"]
SCAN_INTERVAL = "15"  # 15-minute candles

# How many candles to fetch for analysis
LOOKBACK_BARS = 500

# Signal cooldown: don't re-enter same symbol within N seconds
COOLDOWN_SECONDS = 5 * 60  # 5 minutes

# Min R:R ratio to accept a signal
MIN_RR = 1.0

# Trailing stop update interval (seconds)
TRAILING_UPDATE_INTERVAL = 30


def _parse_reduce_thresholds(raw: str) -> list[tuple[float, float]]:
    """Parse '1.5:0.25,2.0:0.25' -> [(1.5, 0.25), (2.0, 0.25)]"""
    result: list[tuple[float, float]] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        r, frac = pair.split(":", 1)
        result.append((float(r), float(frac)))
    return sorted(result, key=lambda x: x[0])


def _cn_now() -> datetime:
    return datetime.now(tz=timezone(timedelta(hours=8)))


class TradingLoop:
    def __init__(
        self,
        engine: PaperEngine,
        event_bus: Optional[EventBroadcaster] = None,
        price_feed: Optional[PriceFeedService] = None,
    ):
        self.engine = engine
        self._event_bus = event_bus
        self._price_feed = price_feed
        self._repo: Optional[BinanceRepository] = None
        self._running = False
        self._last_signal_time: dict[str, float] = {}
        self._scan_count = 0
        self._last_report_date: str = ""
        self._last_optimize_date: str = ""
        self._reduce_thresholds: list[tuple[float, float]] = []
        self._last_trailing_update: float = 0

    async def start(self, scan_seconds: int = 60) -> None:
        self._repo = BinanceRepository()
        self._running = True
        self._reduce_thresholds = _parse_reduce_thresholds(settings.auto_reduce_thresholds)
        log.info("Trading loop started (WS-driven, symbols=%s)", SCAN_SYMBOLS)

        tasks = []

        # Price tick driven position management
        if self._event_bus:
            tick_queue = self._event_bus.subscribe()
            tasks.append(asyncio.create_task(self._price_tick_loop(tick_queue)))

        # Periodic signal scanning
        tasks.append(asyncio.create_task(self._scan_loop(scan_seconds)))

        # Scheduled tasks (report, optimization)
        tasks.append(asyncio.create_task(self._schedule_loop()))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self._running = False
        finally:
            for t in tasks:
                t.cancel()
            if self._event_bus and tick_queue:
                self._event_bus.unsubscribe(tick_queue)

    def stop(self) -> None:
        self._running = False
        log.info("Trading loop stopped after %d scans", self._scan_count)

    # ── Price tick driven position management ──

    async def _price_tick_loop(self, queue: asyncio.Queue) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            if event.get("type") != "price_tick":
                continue
            try:
                await self._manage_position_tick(event["symbol"], event["price"])
            except Exception as e:
                log.warning("Price tick error for %s: %s", event["symbol"], e)

    async def _manage_position_tick(self, symbol: str, price: float) -> None:
        """Every price tick: check SL/TP, auto-reduce, trailing stop."""
        positions = self.engine.get_positions("open") + self.engine.get_positions("partial_closed")
        pos = self._find_position(positions, symbol)
        if pos is None:
            return

        # Check SL/TP
        closed = self.engine.check_sl_tp(symbol, price, price, price)
        if closed:
            await self._publish_position_update()
            return

        # Check auto-reduce
        await self._check_auto_reduce(symbol, price, pos)

        # Update trailing stop periodically
        now_ts = _cn_now().timestamp()
        if now_ts - self._last_trailing_update >= TRAILING_UPDATE_INTERVAL:
            self._last_trailing_update = now_ts
            await self._update_trailing(symbol, pos)

        await self._publish_position_update()

    async def _check_auto_reduce(self, symbol: str, price: float, pos) -> None:
        entry = pos.entry_price
        sl = pos.stop_loss
        risk = abs(entry - sl)
        # After TP1, SL moves to breakeven making risk=0; use original TP1 distance
        if risk <= 0 and pos.take_profit_1:
            risk = abs(pos.take_profit_1 - entry)
        if risk <= 0:
            return

        reductions_done: set[str] = set()
        if hasattr(pos, "reductions_done") and pos.reductions_done:
            try:
                reductions_done = set(json.loads(pos.reductions_done))
            except (json.JSONDecodeError, TypeError):
                pass

        for threshold, fraction in self._reduce_thresholds:
            if pos.side == "LONG":
                r_multiple = (price - entry) / risk
            else:
                r_multiple = (entry - price) / risk

            if r_multiple >= threshold and str(threshold) not in reductions_done:
                pnl = self.engine.reduce_position(pos.position_id, fraction, price)
                if pnl > 0:
                    self.engine.mark_reduction_done(pos.position_id, threshold)
                    if self._event_bus:
                        await self._event_bus.publish_trade_reduced(
                            {"id": pos.position_id, "symbol": symbol},
                            fraction, price, pnl,
                        )
                    log.info("Auto-reduced %s: %.0f%% @ %.2f (R=%.1f), PnL=%.2f",
                             symbol, fraction * 100, price, r_multiple, pnl)
                break

    async def _update_trailing(self, symbol: str, pos) -> None:
        try:
            candles = await self._repo.get_klines_history(symbol, SCAN_INTERVAL, 30)
            if len(candles) < 16:
                return
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            closes = [c.close for c in candles]
            atr_val = atr_last_wilder(highs, lows, closes, 14)
            if pos.side == "LONG":
                peak = pos.peak_price or pos.entry_price
                new_stop = peak - 2.0 * atr_val
                if new_stop > pos.stop_loss:
                    self.engine.update_trailing_stop(pos.position_id, new_stop)
            else:
                trough = pos.trough_price or pos.entry_price
                new_stop = trough + 2.0 * atr_val
                if new_stop < pos.stop_loss:
                    self.engine.update_trailing_stop(pos.position_id, new_stop)
        except Exception as e:
            log.warning("Trailing stop failed for %s: %s", symbol, e)

    # ── Periodic signal scanning ──

    async def _scan_loop(self, scan_seconds: int) -> None:
        while self._running:
            try:
                # Manage existing positions with latest prices
                await self._manage_all_positions()
                # Scan for new signals
                for symbol in SCAN_SYMBOLS:
                    await self._scan_symbol(symbol)
            except Exception as e:
                log.error("Scan cycle error: %s", e, exc_info=True)
            self._scan_count += 1
            await asyncio.sleep(scan_seconds)

    async def _manage_all_positions(self) -> None:
        """Check SL/TP and auto-reduce for all open positions using REST prices."""
        positions = self.engine.get_positions("open") + self.engine.get_positions("partial_closed")
        if not positions:
            return
        for pos in positions:
            try:
                price = await self._fetch_ticker_price(pos.symbol)
                if not price:
                    continue

                # Check SL/TP (use price as both high/low since we only have last price)
                closed = self.engine.check_sl_tp(pos.symbol, price, price, price)
                if closed:
                    log.info("SL/TP triggered for %s %s: closed %d position(s) @ %.2f",
                             pos.symbol, pos.side, len(closed), price)
                    continue

                # Check auto-reduce
                await self._check_auto_reduce(pos.symbol, price, pos)
            except Exception as e:
                log.warning("Position management failed for %s: %s", pos.symbol, e)

    async def _fetch_ticker_price(self, symbol: str) -> float | None:
        """Fetch latest price from Binance ticker API."""
        import httpx
        for base_url in ["https://fapi.binance.com", "https://fapi1.binance.com", "https://fapi2.binance.com"]:
            try:
                async with httpx.AsyncClient(timeout=5.0, trust_env=False, proxy=None) as client:
                    r = await client.get(f"{base_url}/fapi/v1/ticker/price", params={"symbol": symbol})
                    r.raise_for_status()
                    return float(r.json()["price"])
            except Exception:
                continue
        return None

    async def _scan_symbol(self, symbol: str) -> None:
        # Check cooldown
        now_ts = _cn_now().timestamp()
        last = self._last_signal_time.get(symbol, 0)
        if now_ts - last < COOLDOWN_SECONDS:
            return

        # Check daily loss limit (5%)
        summary = self.engine.get_account_summary()
        if summary.daily_pnl < -(summary.initial_equity * 0.05):
            return

        # Fetch candles
        candles = await self._repo.get_klines_history(symbol, SCAN_INTERVAL, LOOKBACK_BARS)
        if len(candles) < 60:
            return

        # Analyze
        try:
            bundle = build_analyze_bundle(
                candles,
                market=Market.CRYPTO,
                symbol=symbol,
                interval=SCAN_INTERVAL,
                higher_strokes=[],
                higher_pivots=[],
            )
        except Exception as e:
            log.warning("Analysis failed for %s: %s", symbol, e)
            return

        # Get latest actionable signal
        sig = self._pick_best_signal(bundle.all_buy_signals, bundle.all_sell_signals)
        if sig is None:
            return

        # Enrich with SL/TP using ATR
        normalized = bundle.response.kline_data
        enriched = enrich_signals_with_sl_tp(
            [sig], [], bundle.response.zhongshus,
            min_rr=MIN_RR, candles=normalized,
        )
        if not enriched or enriched[0].stop_loss is None:
            return

        sig = enriched[0]

        # Check R:R
        if sig.risk_reward_ratio is not None and sig.risk_reward_ratio < MIN_RR:
            return

        # Try to open position
        snapshot = self._build_analysis_snapshot(symbol, sig, bundle, candles, summary)
        pid = self.engine.open_position_from_signal(sig, symbol, analysis_snapshot=snapshot)
        if pid:
            log.info("Opened %s %s position: entry=%.2f sl=%.2f rr=%.1f kind=%s",
                     symbol, "LONG" if sig.side == SignalSide.BUY else "SHORT",
                     sig.price, sig.stop_loss, sig.risk_reward_ratio or 0, sig.kind)
            self._last_signal_time[symbol] = now_ts
            if self._event_bus:
                await self._event_bus.publish_signal_detected(symbol, {
                    "kind": sig.kind, "side": sig.side.value, "price": sig.price,
                    "stop_loss": sig.stop_loss, "position_id": pid,
                })
                await self._publish_position_update()

    # ── Scheduled tasks ──

    async def _schedule_loop(self) -> None:
        while self._running:
            try:
                now = _cn_now()
                today = now.strftime("%Y-%m-%d")

                if now.hour >= 20 and self._last_report_date != today:
                    await self._send_daily_report()
                    self._last_report_date = today

                if now.hour >= 20 and now.minute >= 30 and self._last_optimize_date != today:
                    await self._run_optimization()
                    self._last_optimize_date = today
            except Exception as e:
                log.error("Schedule error: %s", e, exc_info=True)

            await asyncio.sleep(60)

    async def _send_daily_report(self) -> None:
        try:
            from app.services.daily_report import send_daily_report
            msg_id = await send_daily_report(
                self.engine,
                settings.feishu_app_id,
                settings.feishu_app_secret,
                settings.feishu_chat_id,
            )
            if msg_id:
                log.info("Daily report sent: %s", msg_id)
            else:
                log.info("Daily report generated but not sent (Feishu not configured)")
        except Exception as e:
            log.error("Daily report failed: %s", e, exc_info=True)

    async def _run_optimization(self) -> None:
        try:
            from app.services.strategy_optimizer import StrategyOptimizer
            opt = StrategyOptimizer()
            best = await opt.run_optimization(self._repo, max_combos=30)
            if best:
                log.info("Optimization complete. Best score=%.4f params=%s", best.avg_score, best.params)
                await self._send_optimization_result(best)
        except Exception as e:
            log.error("Optimization failed: %s", e, exc_info=True)

    async def _send_optimization_result(self, run) -> None:
        if not settings.feishu_app_id:
            return
        try:
            from app.services.feishu_notify import get_tenant_token, send_card
            card = {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": "策略优化结果"}, "template": "turquoise"},
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": (
                        f"**综合评分**: {run.avg_score:.4f}\n"
                        f"**参数**: ```{run.params}```\n"
                        f"**各标的评分**: {', '.join(f'{k}={v:.3f}' for k, v in run.scores.items())}\n\n"
                        f"请通过 `POST /trade/optimization/approve/{run.run_id}` 审批"
                    )}},
                ],
            }
            token = await get_tenant_token(settings.feishu_app_id, settings.feishu_app_secret)
            await send_card(token, settings.feishu_chat_id, card)
        except Exception as e:
            log.warning("Failed to send optimization result: %s", e)

    # ── Helpers ──

    @staticmethod
    def _build_analysis_snapshot(
        symbol: str, sig: Signal, bundle, candles, account_summary,
    ) -> dict:
        """Capture analysis context at trade entry for journal/review."""
        resp = bundle.response
        zhongshus = resp.zhongshus or []
        divergences = resp.divergences or []

        recent_candles = candles[-20:] if len(candles) >= 20 else candles
        recent_high = max(c.high for c in recent_candles) if recent_candles else 0
        recent_low = min(c.low for c in recent_candles) if recent_candles else 0

        try:
            atr_val = atr_last_wilder(
                [c.high for c in candles[-30:]],
                [c.low for c in candles[-30:]],
                [c.close for c in candles[-30:]],
                14,
            )
        except Exception:
            atr_val = 0

        # Summarize last few zhongshus near the signal
        zs_summary = []
        for zs in zhongshus[-3:]:
            zs_summary.append({
                "zd": zs.zd if hasattr(zs, "zd") else None,
                "zg": zs.zg if hasattr(zs, "zg") else None,
                "direction": zs.direction if hasattr(zs, "direction") else None,
            })

        # Summarize divergences
        div_summary = []
        for d in divergences[-3:]:
            div_summary.append({
                "kind": d.kind if hasattr(d, "kind") else None,
                "direction": d.direction if hasattr(d, "direction") else None,
            })

        return {
            "signal": {
                "kind": sig.kind,
                "side": sig.side.value,
                "strength": sig.strength,
                "idx": sig.idx,
            },
            "structure": {
                "zhongshu_count": len(zhongshus),
                "zhongshu_recent": zs_summary,
                "divergence_count": len(divergences),
                "divergence_recent": div_summary,
            },
            "market": {
                "interval": SCAN_INTERVAL,
                "lookback_bars": len(candles),
                "recent_high": recent_high,
                "recent_low": recent_low,
                "atr_14": round(atr_val, 4),
            },
            "risk": {
                "daily_pnl": round(account_summary.daily_pnl, 2),
                "open_positions": account_summary.open_positions,
                "available_balance": round(account_summary.available_balance, 2),
            },
        }

    @staticmethod
    def _find_position(positions, symbol: str):
        for p in positions:
            if p.symbol == symbol:
                return p
        return None

    async def _publish_position_update(self) -> None:
        if not self._event_bus:
            return
        positions = [
            p.model_dump() for p in
            self.engine.get_positions("open") + self.engine.get_positions("partial_closed")
        ]
        account = self.engine.get_account_summary().model_dump()
        await self._event_bus.publish_position_update(positions, account)

    def _pick_best_signal(self, buys: list[Signal], sells: list[Signal]) -> Optional[Signal]:
        """Pick the strongest recent signal (latest, unfiltered, with stop_loss)."""
        candidates = [s for s in buys + sells if not s.rr_filtered and s.stop_loss is not None]
        if not candidates:
            return None
        candidates.sort(key=lambda s: s.idx, reverse=True)
        latest_idx = candidates[0].idx
        recent = [s for s in candidates if s.idx >= latest_idx - 3]
        kind_priority = {"first": 0, "second": 1, "second_extend": 2, "second_class": 3, "third": 4, "third_class": 5}
        recent.sort(key=lambda s: (kind_priority.get(s.kind, 9), -s.idx))
        return recent[0] if recent else None

    # ── Legacy candle-based position management (used by tests) ──

    async def _manage_position(self, symbol: str, candles: list) -> None:
        """Update trailing stop and check SL/TP for existing position using candle data."""
        positions = self.engine.get_positions("open") + self.engine.get_positions("partial_closed")
        pos = self._find_position(positions, symbol)
        if pos is None:
            return

        latest = candles[-1]
        self.engine.check_sl_tp(symbol, latest.high, latest.low, latest.close)

        positions = self.engine.get_positions("open") + self.engine.get_positions("partial_closed")
        pos = self._find_position(positions, symbol)
        if pos is None:
            return

        if len(candles) > 16:
            try:
                highs = [c.high for c in candles]
                lows = [c.low for c in candles]
                closes = [c.close for c in candles]
                atr_val = atr_last_wilder(highs, lows, closes, 14)
                if pos.side == "LONG":
                    peak = pos.peak_price or pos.entry_price
                    new_stop = peak - 2.0 * atr_val
                    if new_stop > pos.stop_loss:
                        self.engine.update_trailing_stop(pos.position_id, new_stop)
                else:
                    trough = pos.trough_price or pos.entry_price
                    new_stop = trough + 2.0 * atr_val
                    if new_stop < pos.stop_loss:
                        self.engine.update_trailing_stop(pos.position_id, new_stop)
            except Exception as e:
                log.warning("Trailing stop update failed for %s: %s", symbol, e)
