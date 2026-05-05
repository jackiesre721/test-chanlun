from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.dependencies import get_analyzer_service, get_market_repository
from app.core.config import settings
from app.core.models import (
    AiStructureHintRequest,
    AiStructureHintResponse,
    AiVerdictResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    BarAggregateRequest,
    BarAggregateResponse,
    MultiAnalyzeRequest,
    MultiAnalyzeResponse,
    PaperOrderRequest,
    PaperOrderResponse,
    PositionSizingRequest,
    PositionSizingResponse,
    QuickBacktestRequest,
    QuickBacktestResponse,
    SymbolResponse,
    TrailingStopRequest,
    TrailingStopResponse,
)
from app.repositories.market_data import BinanceRepository
from app.services.bar_generator import aggregate_candles_to_minutes
from app.services.analyzer import AnalyzerService
from app.services.ai_glm_verdict import verdict_from_analyze_payload
from app.services.ai_structure_hint import structure_hint
from app.services.backtest_quick import run_quick_backtest
from app.services.risk_controls import compute_position_size, compute_trailing_stop
from app.services import symbol_registry
from app.trading.paper_orders import recent_orders, record_paper_order

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
    return SymbolResponse(
        symbols=sorted(symbol_registry.get_symbols()),
        registry_degraded=symbol_registry.is_registry_degraded(),
    )


@router.post("/tools/aggregate-bars", response_model=BarAggregateResponse)
def aggregate_bars(payload: BarAggregateRequest) -> BarAggregateResponse:
    if not payload.candles:
        raise HTTPException(status_code=400, detail="candles must be non-empty")
    out = aggregate_candles_to_minutes(payload.candles, payload.target_interval_minutes)
    return BarAggregateResponse(candles=out)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    service: AnalyzerService = Depends(get_analyzer_service),
) -> AnalyzeResponse:
    return await service.analyze(payload)


@router.post("/analyze/multi", response_model=MultiAnalyzeResponse)
async def analyze_multi(
    payload: MultiAnalyzeRequest,
    service: AnalyzerService = Depends(get_analyzer_service),
) -> MultiAnalyzeResponse:
    return await service.analyze_multi(payload)


@router.post("/backtest/quick", response_model=QuickBacktestResponse)
async def quick_backtest(
    payload: QuickBacktestRequest,
    repository: BinanceRepository = Depends(get_market_repository),
) -> QuickBacktestResponse:
    try:
        return await run_quick_backtest(repository, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/risk/position-size", response_model=PositionSizingResponse)
def position_size(payload: PositionSizingRequest) -> PositionSizingResponse:
    try:
        return compute_position_size(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/risk/trailing-stop", response_model=TrailingStopResponse)
def trailing_stop(payload: TrailingStopRequest) -> TrailingStopResponse:
    try:
        return compute_trailing_stop(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/trade/paper", response_model=PaperOrderResponse)
def trade_paper(payload: PaperOrderRequest) -> PaperOrderResponse:
    if not settings.paper_trading_enabled:
        return PaperOrderResponse(
            accepted=False,
            reason="Paper trading disabled (set CHANLAN_PAPER_TRADING_ENABLED=true).",
        )
    oid = record_paper_order(
        symbol=payload.symbol,
        side=payload.side,
        quantity=payload.quantity,
        note=payload.note,
    )
    return PaperOrderResponse(
        accepted=True,
        reason="Recorded to local SQLite paper log only (not sent to any exchange).",
        order_id=oid,
    )


@router.get("/trade/paper/recent")
def trade_paper_recent(limit: int = 50) -> dict[str, object]:
    capped = max(1, min(limit, 200))
    return {"orders": recent_orders(capped)}


@router.post("/ai/structure-hint", response_model=AiStructureHintResponse)
def ai_structure_hint(payload: AiStructureHintRequest) -> AiStructureHintResponse:
    return structure_hint(payload)


@router.post("/analyze/verdict", response_model=AiVerdictResponse)
@router.post("/ai/verdict", response_model=AiVerdictResponse)
@router.post("/api/ai/verdict", response_model=AiVerdictResponse)
async def ai_verdict(body: dict[str, Any] = Body(...)) -> AiVerdictResponse:
    """缠论分析 JSON + 可选元字段：`glm_api_key`、`glm_model`、`glm_full_context`（会与分析字段剥离后校验）。
    全量语境时建议带上完整 `kline_data` / `macd_data` 等以便服务端拼 K 尾与结构；智谱返回偏多/偏空及**参考价位**（非投资建议）。

    同时挂载 `/analyze/verdict`、`/api/ai/verdict`：部分网关只转发 `/analyze` 或 `/api/*`，避免仅 `/ai/verdict` 返回 404。"""
    return await verdict_from_analyze_payload(body)
