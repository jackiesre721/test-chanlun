import asyncio
import logging
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    _DISPLAY_TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # pragma: no cover — 极简环境缺少 tzdata 时退回固定 UTC+8
    _DISPLAY_TZ = timezone(timedelta(hours=8))
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.errors import MarketDataError
from app.core.models import Candle

log = logging.getLogger(__name__)

BINANCE_INTERVALS = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "1440": "1d",
    "10080": "1w",
    "43200": "1M",
}

# Internal interval code -> candle width in milliseconds
_INTERVAL_MS = {
    "1": 60_000,
    "5": 300_000,
    "15": 900_000,
    "30": 1_800_000,
    "60": 3_600_000,
    "240": 14_400_000,
    "1440": 86_400_000,
    "10080": 604_800_000,
    "43200": 2_592_000_000,
}

BINANCE_FUTURES_BASE_URLS = (
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
)


class BinanceRepository:
    """Read-only Binance market data access with optional PG cache."""

    def __init__(
        self,
        base_url: str = settings.binance_futures_base_url,
        pg_session_factory: Any = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._pg_factory = pg_session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
        end_time_ms: Optional[int] = None,
    ) -> list[Candle]:
        binance_interval = BINANCE_INTERVALS.get(interval)
        if binance_interval is None:
            raise MarketDataError(f"Unsupported interval: {interval}")

        if self._pg_factory:
            candles = await self._get_klines_from_pg(symbol, interval, limit, end_time_ms)
            if len(candles) == limit:
                return candles

        candles = await self._fetch_klines_from_binance(symbol, interval, limit, end_time_ms)

        if self._pg_factory and candles:
            asyncio.create_task(self._persist_klines(symbol, interval, candles))

        return candles

    async def get_klines_history(self, symbol: str, interval: str, max_bars: int) -> list[Candle]:
        target = max(1, min(max_bars, settings.backtest_max_bars))

        if self._pg_factory:
            pg_candles = await self._get_klines_from_pg(symbol, interval, target)
            if len(pg_candles) >= target:
                freshness_ms = _INTERVAL_MS.get(interval, 60_000) * 2
                latest = pg_candles[-1].open_time
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                if now_ms - latest <= freshness_ms:
                    return pg_candles[-target:]

            if pg_candles:
                tail = await self._fetch_tail_gap(symbol, interval, target, pg_candles)
                return tail

        merged = await self._paginate_binance(symbol, interval, target)

        if self._pg_factory and merged:
            asyncio.create_task(self._persist_klines(symbol, interval, merged))

        return merged

    async def get_klines_history_from_time(
        self, symbol: str, interval: str, start_time_ms: int
    ) -> list[Candle]:
        """Fetch klines from *start_time_ms* up to now, paginating forward."""
        binance_interval = BINANCE_INTERVALS[interval]
        width_ms = _INTERVAL_MS.get(interval, 60_000)
        max_bars = settings.backtest_max_bars
        merged: list[Candle] = []
        cursor = int(start_time_ms)

        while len(merged) < max_bars:
            chunk = min(settings.max_klines_limit, max_bars - len(merged))
            params: dict[str, Any] = {
                "symbol": symbol,
                "interval": binance_interval,
                "limit": chunk,
                "startTime": cursor,
            }
            data = await self._get_json("/fapi/v1/klines", params=params)
            if not isinstance(data, list) or not data:
                break
            batch = [self._parse_candle(len(merged) + i, row) for i, row in enumerate(data)]
            merged.extend(batch)
            last_open = int(data[-1][0])
            cursor = last_open + width_ms
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            if cursor > now_ms or len(data) < chunk:
                break

        if len(merged) > max_bars:
            merged = merged[:max_bars]
        return [
            c.model_copy(update={"source_idx": i, "high_idx": i, "low_idx": i})
            for i, c in enumerate(merged)
        ]

    async def get_symbols(self) -> list[str]:
        data = await self._get_json("/fapi/v1/exchangeInfo", params=None)
        symbols = [
            item["symbol"]
            for item in data.get("symbols", [])
            if item.get("status") == "TRADING" and item.get("quoteAsset") == "USDT"
        ]
        return sorted(symbols)

    # ------------------------------------------------------------------
    # PG helpers
    # ------------------------------------------------------------------

    async def _get_klines_from_pg(
        self, symbol: str, interval: str, limit: int, end_time_ms: Optional[int] = None
    ) -> list[Candle]:
        from app.db.kline_store import fetch_klines

        try:
            async with self._pg_factory() as session:
                rows = await fetch_klines(session, symbol, BINANCE_INTERVALS[interval], limit, end_time_ms)
        except Exception:
            log.warning("PG read failed for %s/%s, falling back to Binance", symbol, interval, exc_info=True)
            return []
        return [self._row_to_candle(idx, r) for idx, r in enumerate(rows)]

    async def _persist_klines(self, symbol: str, interval: str, candles: list[Candle]) -> None:
        from app.db.kline_store import upsert_klines

        bi = BINANCE_INTERVALS[interval]
        rows = [(c.open_time, c.open, c.high, c.low, c.close, c.volume) for c in candles]
        try:
            async with self._pg_factory() as session:
                n = await upsert_klines(session, symbol, bi, rows)
                if n:
                    log.info("PG upserted %d klines for %s/%s", n, symbol, bi)
        except Exception:
            log.warning("PG persist failed for %s/%s", symbol, bi, exc_info=True)

    async def _fetch_tail_gap(
        self, symbol: str, interval: str, target: int, pg_candles: list[Candle]
    ) -> list[Candle]:
        bi = BINANCE_INTERVALS[interval]
        latest_pg_time = pg_candles[-1].open_time
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        gap_ms = now_ms - latest_pg_time
        width_ms = _INTERVAL_MS.get(interval, 60_000)
        gap_bars = min(int(gap_ms / width_ms) + 2, 1500)

        if gap_bars <= 0:
            return pg_candles[-target:]

        tail = await self._fetch_klines_from_binance(symbol, interval, gap_bars)
        if not tail:
            return pg_candles[-target:]

        if self._pg_factory:
            asyncio.create_task(self._persist_klines(symbol, interval, tail))

        combined = pg_candles + tail
        seen: set[int] = set()
        deduped: list[Candle] = []
        for c in combined:
            if c.open_time not in seen:
                seen.add(c.open_time)
                deduped.append(c)
        deduped.sort(key=lambda c: c.open_time)
        if len(deduped) > target:
            deduped = deduped[-target:]
        return [
            c.model_copy(update={"source_idx": i, "high_idx": i, "low_idx": i})
            for i, c in enumerate(deduped)
        ]

    @staticmethod
    def _row_to_candle(idx: int, row: tuple) -> Candle:
        open_time = int(row[0])
        dt = datetime.fromtimestamp(open_time / 1000, tz=_DISPLAY_TZ)
        return Candle(
            open_time=open_time,
            time=dt.strftime("%m-%d %H:%M"),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            source_idx=idx,
            high_idx=idx,
            low_idx=idx,
        )

    # ------------------------------------------------------------------
    # Binance API helpers (unchanged logic, extracted)
    # ------------------------------------------------------------------

    async def _fetch_klines_from_binance(
        self, symbol: str, interval: str, limit: int, end_time_ms: Optional[int] = None
    ) -> list[Candle]:
        binance_interval = BINANCE_INTERVALS[interval]
        params: dict[str, Any] = {"symbol": symbol, "interval": binance_interval, "limit": limit}
        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)
        data = await self._get_json("/fapi/v1/klines", params=params)
        if not isinstance(data, list):
            raise MarketDataError("Unexpected kline response from Binance")
        return [self._parse_candle(idx, row) for idx, row in enumerate(data)]

    async def _paginate_binance(self, symbol: str, interval: str, target: int) -> list[Candle]:
        merged: list[Candle] = []
        end_before: Optional[int] = None
        seen_open_times: set[int] = set()

        while len(merged) < target:
            chunk_limit = min(settings.max_klines_limit, target - len(merged))
            batch = await self._fetch_klines_from_binance(symbol, interval, chunk_limit, end_time_ms=end_before)
            if not batch:
                break

            oldest_open_time = batch[0].open_time
            deduped_forward: list[Candle] = []
            for candle in batch:
                if candle.open_time in seen_open_times:
                    continue
                seen_open_times.add(candle.open_time)
                deduped_forward.append(candle)

            if not deduped_forward:
                break

            merged = deduped_forward + merged
            end_before = oldest_open_time - 1

            if len(batch) < chunk_limit:
                break

        merged.sort(key=lambda c: c.open_time)
        if len(merged) > target:
            merged = merged[-target:]
        return [
            candle.model_copy(update={"source_idx": idx, "high_idx": idx, "low_idx": idx})
            for idx, candle in enumerate(merged)
        ]

    async def _get_json(self, path: str, params: Optional[dict[str, Any]]) -> Any:
        last_error = "unknown error"
        base_urls = (self._base_url,) + tuple(url for url in BINANCE_FUTURES_BASE_URLS if url != self._base_url)
        for base_url in base_urls:
            try:
                async with httpx.AsyncClient(
                    base_url=base_url,
                    timeout=settings.request_timeout_seconds,
                    trust_env=False,
                    proxy=None,
                ) as client:
                    response = await client.get(path, params=params)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text[:240] if exc.response is not None else exc.__class__.__name__
                last_error = f"{base_url}: {detail}"
            except httpx.HTTPError as exc:
                detail = str(exc) or exc.__class__.__name__
                last_error = f"{base_url}: {detail}"
        raise MarketDataError(f"Market data request failed after retries: {last_error}")

    @staticmethod
    def _parse_candle(idx: int, row: list[Any]) -> Candle:
        open_time = int(row[0])
        dt = datetime.fromtimestamp(open_time / 1000, tz=_DISPLAY_TZ)
        return Candle(
            open_time=open_time,
            time=dt.strftime("%m-%d %H:%M"),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            source_idx=idx,
            high_idx=idx,
            low_idx=idx,
        )
