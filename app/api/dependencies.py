from fastapi import Depends

from app.repositories.market_data import BinanceRepository
from app.services.analyzer import AnalyzerService


def get_market_repository() -> BinanceRepository:
    return BinanceRepository()


def get_analyzer_service(repository: BinanceRepository = Depends(get_market_repository)) -> AnalyzerService:
    return AnalyzerService(repository)
