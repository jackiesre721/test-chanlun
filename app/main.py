import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.db.engine import close_db, init_db, pg_available, session_factory

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / settings.static_dir

_sync_task: Optional[asyncio.Task] = None
_trading_task: Optional[asyncio.Task] = None
_price_feed_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sync_task
    from app.services import symbol_registry
    from app.repositories.market_data import BinanceRepository

    repo = BinanceRepository()
    await symbol_registry.refresh_symbols(repo)
    log.info("Symbol registry loaded: %d pairs", len(symbol_registry.get_symbols()))

    if pg_available():
        await init_db()
        log.info("PostgreSQL connected, klines table ready")
        if settings.sync_enabled:
            from app.db.ws_listener import start_ws_listener

            _sync_task = asyncio.create_task(start_ws_listener())

    # Initialize EventBus for WebSocket broadcasting
    from app.services.event_bus import EventBroadcaster
    event_bus = EventBroadcaster()
    from app.api.routes import set_event_bus
    set_event_bus(event_bus)
    log.info("EventBus initialized")

    # Start price feed (Binance @bookTicker)
    from app.services.price_feed import PriceFeedService
    _price_feed = PriceFeedService(event_bus)
    _price_feed_task = asyncio.create_task(_price_feed.start())
    from app.api.routes import set_price_feed
    set_price_feed(_price_feed)
    log.info("Price feed scheduled")

    # Start paper trading loop
    if settings.paper_trading_enabled:
        from app.services.trading_loop import TradingLoop
        from app.trading.paper_engine import PaperEngine

        _engine = PaperEngine(
            initial_equity=settings.trading_initial_equity,
            leverage=settings.trading_leverage,
            risk_fraction=settings.trading_risk_fraction,
            max_positions=settings.trading_max_positions,
        )
        _loop = TradingLoop(_engine, event_bus=event_bus, price_feed=_price_feed)
        _trading_task = asyncio.create_task(_loop.start(scan_seconds=settings.trading_scan_seconds))
        log.info("Paper trading loop scheduled")

    yield
    if _trading_task is not None:
        _trading_task.cancel()
        try:
            await _trading_task
        except asyncio.CancelledError:
            pass
    if _price_feed_task is not None:
        _price_feed.cancel()
        _price_feed_task.cancel()
        try:
            await _price_feed_task
        except asyncio.CancelledError:
            pass
    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
