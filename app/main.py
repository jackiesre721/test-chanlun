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
    yield
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
