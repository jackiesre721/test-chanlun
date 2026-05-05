from fastapi import Depends

from app.db.engine import pg_available, session_factory
from app.repositories.market_data import BinanceRepository
from app.services.analyzer import AnalyzerService


def get_market_repository() -> BinanceRepository:
    factory = session_factory() if pg_available() else None
    return BinanceRepository(pg_session_factory=factory)


def get_analyzer_service(repository: BinanceRepository = Depends(get_market_repository)) -> AnalyzerService:
    return AnalyzerService(repository)
