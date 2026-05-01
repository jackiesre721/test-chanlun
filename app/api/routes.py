from fastapi import APIRouter, Depends

from app.api.dependencies import get_analyzer_service, get_market_repository
from app.core.models import AnalyzeRequest, AnalyzeResponse, SUPPORTED_SYMBOLS, SymbolResponse
from app.repositories.market_data import BinanceRepository
from app.services.analyzer import AnalyzerService

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/symbols", response_model=SymbolResponse)
async def symbols(
    market: str = "crypto",
    repository: BinanceRepository = Depends(get_market_repository),
) -> SymbolResponse:
    if market != "crypto":
        return SymbolResponse(symbols=[])
    return SymbolResponse(symbols=sorted(SUPPORTED_SYMBOLS))


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    service: AnalyzerService = Depends(get_analyzer_service),
) -> AnalyzeResponse:
    return await service.analyze(payload)
