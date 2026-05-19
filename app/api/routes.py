import asyncio
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket, WebSocketDisconnect

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
from app.trading.paper_engine import PaperEngine
from app.services.daily_report import build_daily_report, send_daily_report
from app.services.strategy_optimizer import StrategyOptimizer
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


# ── Paper Trading Engine ──

_engine = PaperEngine(
    initial_equity=settings.trading_initial_equity,
    leverage=settings.trading_leverage,
    risk_fraction=settings.trading_risk_fraction,
    max_positions=settings.trading_max_positions,
)

_price_feed: object | None = None


def set_price_feed(feed) -> None:
    global _price_feed
    _price_feed = feed


@router.get("/trade/account")
def trade_account() -> dict:
    prices = _price_feed.get_all_prices() if _price_feed else None
    return _engine.get_account_summary(prices).model_dump()


@router.get("/trade/positions")
def trade_positions(status: str | None = None) -> dict:
    return {"positions": [p.model_dump() for p in _engine.get_positions(status)]}


@router.get("/trade/orders")
def trade_orders(limit: int = 100) -> dict:
    return {"orders": [o.model_dump() for o in _engine.get_orders(limit)]}


@router.get("/trade/journal")
def trade_journal(limit: int = 50, symbol: str | None = None) -> dict:
    return {"journal": _engine.get_trade_journal(limit, symbol)}


@router.post("/trade/journal/{position_id}/review")
def trade_journal_review(position_id: str, tags: str = "", notes: str = "") -> dict:
    if _engine.update_trade_review(position_id, tags, notes):
        return {"updated": True, "position_id": position_id}
    raise HTTPException(status_code=404, detail="Journal entry not found")


@router.post("/trade/close/{position_id}")
def trade_close(position_id: str, exit_price: float) -> dict:
    positions = _engine.get_positions()
    found = [p for p in positions if p.position_id == position_id and p.status in ("open", "partial_closed")]
    if not found:
        raise HTTPException(status_code=404, detail="Position not found or already closed")
    pnl = _engine.close_position(position_id, exit_price, "manual")
    return {"position_id": position_id, "realized_pnl": pnl, "status": "closed"}


@router.get("/trade/report")
def trade_report() -> dict:
    return build_daily_report(_engine)


@router.post("/trade/report/send")
async def trade_report_send() -> dict:
    msg_id = await send_daily_report(
        _engine,
        settings.feishu_app_id,
        settings.feishu_app_secret,
        settings.feishu_chat_id,
    )
    if msg_id:
        return {"sent": True, "message_id": msg_id}
    return {"sent": False, "reason": "Feishu not configured or send failed"}


# ── Strategy Optimizer ──

_optimizer = StrategyOptimizer()


@router.get("/trade/optimization/results")
def optimization_results(limit: int = 20) -> dict:
    return {"runs": _optimizer.get_all_runs(limit)}


@router.get("/trade/optimization/best")
def optimization_best() -> dict:
    best = _optimizer.get_best()
    if not best:
        return {"best": None}
    return {
        "run_id": best.run_id,
        "params": best.params,
        "avg_score": round(best.avg_score, 4),
        "scores": {k: round(v, 4) for k, v in best.scores.items()},
        "status": best.status,
    }


@router.post("/trade/optimization/run")
async def optimization_run(repository: BinanceRepository = Depends(get_market_repository)) -> dict:
    best = await _optimizer.run_optimization(repository)
    if not best:
        raise HTTPException(status_code=500, detail="Optimization produced no results")
    return {
        "run_id": best.run_id,
        "params": best.params,
        "avg_score": round(best.avg_score, 4),
        "status": "pending_approval",
    }


@router.post("/trade/optimization/approve/{run_id}")
def optimization_approve(run_id: str) -> dict:
    if _optimizer.approve(run_id):
        return {"approved": True, "run_id": run_id}
    raise HTTPException(status_code=404, detail="Run not found or not pending")


@router.post("/trade/optimization/reject/{run_id}")
def optimization_reject(run_id: str) -> dict:
    if _optimizer.reject(run_id):
        return {"rejected": True, "run_id": run_id}
    raise HTTPException(status_code=404, detail="Run not found or not pending")


# ── WebSocket ──

_event_bus = None


def set_event_bus(bus) -> None:
    global _event_bus
    _event_bus = bus


@router.websocket("/ws/trading")
async def ws_trading(websocket: WebSocket) -> None:
    await websocket.accept()
    if _event_bus is None:
        await websocket.send_json({"type": "error", "message": "EventBus not initialized"})
        await websocket.close()
        return

    queue = _event_bus.subscribe()
    try:
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _event_bus.unsubscribe(queue)
