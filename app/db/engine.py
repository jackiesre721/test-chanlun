from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def pg_available() -> bool:
    return bool(settings.database_url)


def _ensure_engine():
    global _engine, _session_factory
    if _engine is None and pg_available():
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_min_size,
            max_overflow=settings.db_pool_max_size - settings.db_pool_min_size,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    if not pg_available():
        return
    _ensure_engine()
    from sqlalchemy import text

    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS klines (
                symbol       TEXT    NOT NULL,
                interval     TEXT    NOT NULL,
                open_time    BIGINT  NOT NULL,
                open         DOUBLE PRECISION NOT NULL,
                high         DOUBLE PRECISION NOT NULL,
                low          DOUBLE PRECISION NOT NULL,
                close        DOUBLE PRECISION NOT NULL,
                volume       DOUBLE PRECISION NOT NULL,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (symbol, interval, open_time)
            )
        """))


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def session_factory() -> async_sessionmaker[AsyncSession] | None:
    if not pg_available():
        return None
    _ensure_engine()
    return _session_factory
