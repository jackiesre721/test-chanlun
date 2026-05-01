from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.errors import MarketDataError
from app.core.models import Candle


BINANCE_INTERVALS = {
    "1": "1m",
    "15": "15m",
    "30": "30m",
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

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        binance_interval = BINANCE_INTERVALS.get(interval)
        if binance_interval is None:
            raise MarketDataError(f"Unsupported interval: {interval}")

        params = {"symbol": symbol, "interval": binance_interval, "limit": limit}
        data = await self._get_json("/api/v3/klines", params=params)
        if not isinstance(data, list):
            raise MarketDataError("Unexpected kline response from Binance")
        return [self._parse_candle(idx, row) for idx, row in enumerate(data)]

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
        dt = datetime.fromtimestamp(open_time / 1000, tz=timezone.utc)
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
