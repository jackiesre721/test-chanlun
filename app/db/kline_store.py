from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_klines(
    session: AsyncSession,
    symbol: str,
    interval: str,
    limit: int,
    end_time_ms: Optional[int] = None,
) -> list[tuple]:
    if end_time_ms is not None:
        sql = text("""
            SELECT open_time, open, high, low, close, volume
            FROM klines
            WHERE symbol = :symbol AND interval = :interval AND open_time <= :end_time
            ORDER BY open_time DESC
            LIMIT :limit
        """)
        params = {"symbol": symbol, "interval": interval, "limit": limit, "end_time": end_time_ms}
    else:
        sql = text("""
            SELECT open_time, open, high, low, close, volume
            FROM klines
            WHERE symbol = :symbol AND interval = :interval
            ORDER BY open_time DESC
            LIMIT :limit
        """)
        params = {"symbol": symbol, "interval": interval, "limit": limit}
    result = await session.execute(sql, params)
    rows = result.all()
    rows.reverse()
    return [(r.open_time, r.open, r.high, r.low, r.close, r.volume) for r in rows]


async def upsert_klines(
    session: AsyncSession,
    symbol: str,
    interval: str,
    rows: list[tuple[int, float, float, float, float, float]],
) -> int:
    if not rows:
        return 0
    sql = text("""
        INSERT INTO klines (symbol, interval, open_time, open, high, low, close, volume)
        VALUES (:symbol, :interval, :open_time, :open, :high, :low, :close, :volume)
        ON CONFLICT (symbol, interval, open_time)
        DO UPDATE SET high = EXCLUDED.high, low = EXCLUDED.low,
                      close = EXCLUDED.close, volume = EXCLUDED.volume
    """)
    params = [
        {
            "symbol": symbol,
            "interval": interval,
            "open_time": r[0],
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5],
        }
        for r in rows
    ]
    result = await session.execute(sql, params)
    await session.commit()
    return result.rowcount


async def latest_open_time(
    session: AsyncSession,
    symbol: str,
    interval: str,
) -> Optional[int]:
    sql = text("""
        SELECT MAX(open_time) AS t FROM klines WHERE symbol = :symbol AND interval = :interval
    """)
    result = await session.execute(sql, {"symbol": symbol, "interval": interval})
    row = result.first()
    return row.t if row and row.t is not None else None


async def count_klines(
    session: AsyncSession,
    symbol: str,
    interval: str,
) -> int:
    sql = text("SELECT COUNT(*) AS c FROM klines WHERE symbol = :symbol AND interval = :interval")
    result = await session.execute(sql, {"symbol": symbol, "interval": interval})
    row = result.first()
    return row.c if row else 0


async def prune_old_klines(
    session: AsyncSession,
    retention_days: int,
) -> int:
    sql = text("""
        DELETE FROM klines WHERE open_time < (EXTRACT(EPOCH FROM now()) * 1000 - :days * 86400000)::bigint
    """)
    result = await session.execute(sql, {"days": retention_days})
    await session.commit()
    return result.rowcount
