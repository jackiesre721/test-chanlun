"""CLI: python -m app.db.backfill_cli [--days 30] [--symbol BTCUSDT] [--interval 1m]"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill kline data into PostgreSQL")
    parser.add_argument("--days", type=int, default=None, help="Days of history (default: from config)")
    parser.add_argument("--symbol", type=str, default=None, help="Single symbol (default: all)")
    parser.add_argument("--interval", type=str, default=None, help="Single interval code (default: all)")
    args = parser.parse_args()

    from app.core.config import settings

    if not settings.database_url:
        print("Error: CHANLAN_DATABASE_URL is not set", file=sys.stderr)
        sys.exit(1)

    if args.symbol:
        from app.services import symbol_registry

        symbol_registry._symbols = {args.symbol}
        symbol_registry._expires_at = 0.0
    if args.interval:
        from app.repositories.market_data import BINANCE_INTERVALS

        single = {args.interval: BINANCE_INTERVALS[args.interval]}
        BINANCE_INTERVALS.clear()
        BINANCE_INTERVALS.update(single)

    async def _run() -> None:
        from app.db.engine import init_db
        from app.db.sync import backfill

        await init_db()
        await backfill(days=args.days)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
