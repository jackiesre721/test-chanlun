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


BINANCE_INTERVALS = {
    "1": "1m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "1440": "1d",
}

BINANCE_BASE_URLS = (
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
)


class BinanceRepository:
    """Read-only Binance market data access."""

    def __init__(self, base_url: str = settings.binance_base_url) -> None:
        self._base_url = base_url.rstrip("/")

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

        params: dict[str, Any] = {"symbol": symbol, "interval": binance_interval, "limit": limit}
        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)
        data = await self._get_json("/api/v3/klines", params=params)
        if not isinstance(data, list):
            raise MarketDataError("Unexpected kline response from Binance")
        return [self._parse_candle(idx, row) for idx, row in enumerate(data)]

    async def get_klines_history(self, symbol: str, interval: str, max_bars: int) -> list[Candle]:
        """分页拉取至多 max_bars 根 K 线（按时间升序，含当前最新一根）。"""
        target = max(1, min(max_bars, settings.backtest_max_bars))
        merged: list[Candle] = []
        end_before: Optional[int] = None
        seen_open_times: set[int] = set()

        while len(merged) < target:
            chunk_limit = min(settings.max_klines_limit, target - len(merged))
            batch = await self.get_klines(symbol, interval, chunk_limit, end_time_ms=end_before)
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

    async def get_symbols(self) -> list[str]:
        data = await self._get_json("/api/v3/exchangeInfo", params=None)
        symbols = [
            item["symbol"]
            for item in data.get("symbols", [])
            if item.get("status") == "TRADING" and item.get("quoteAsset") == "USDT"
        ]
        return sorted(symbols)

    async def _get_json(self, path: str, params: Optional[dict[str, Any]]) -> Any:
        last_error = "unknown error"
        base_urls = (self._base_url,) + tuple(url for url in BINANCE_BASE_URLS if url != self._base_url)
        for base_url in base_urls:
            try:
                async with httpx.AsyncClient(
                    base_url=base_url,
                    timeout=settings.request_timeout_seconds,
                    trust_env=False,
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
