"""可选磁盘缓存：在「品种 / 周期 / 深度 / 线段引擎 / 规则版本 / K 线锚点」一致时复用上一次的 AnalyzeResponse。

- 锚点：Binance 最新一根 K 的 open_time（与分页拉满后的末端对齐）；新 bar 生成后自动失效。
- 开启 inline ``glm_verdict`` 时不写入、不读取缓存（避免省略 AI 调用）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.models import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_pipeline import RULES_VERSION


def _cache_dir() -> Path:
    raw = Path(settings.analyze_disk_cache_dir).expanduser()
    return raw if raw.is_absolute() else Path.cwd() / raw


def _cache_key(
    *,
    symbol: str,
    interval: str,
    eff_limit: int,
    segment_engine: str,
    anchor_open_time_ms: int,
) -> str:
    raw = f"{symbol}|{interval}|{eff_limit}|{segment_engine}|{RULES_VERSION}|{anchor_open_time_ms}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def load_cached_analyze_result(
    *,
    request: AnalyzeRequest,
    eff_limit: int,
    anchor_open_time_ms: int,
) -> Optional[AnalyzeResponse]:
    if not settings.analyze_disk_cache_enabled:
        return None
    if request.glm_verdict is not None:
        return None
    key = _cache_key(
        symbol=request.symbol,
        interval=request.interval,
        eff_limit=eff_limit,
        segment_engine=settings.segment_engine,
        anchor_open_time_ms=anchor_open_time_ms,
    )
    path = _cache_path(key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rec_anchor = int(payload.get("anchor_open_time_ms", -1))
        if rec_anchor != anchor_open_time_ms:
            return None
        return AnalyzeResponse.model_validate(payload.get("response"))
    except Exception:
        return None


def save_cached_analyze_result(
    *,
    request: AnalyzeRequest,
    eff_limit: int,
    anchor_open_time_ms: int,
    response: AnalyzeResponse,
) -> None:
    if not settings.analyze_disk_cache_enabled:
        return
    if request.glm_verdict is not None:
        return
    key = _cache_key(
        symbol=request.symbol,
        interval=request.interval,
        eff_limit=eff_limit,
        segment_engine=settings.segment_engine,
        anchor_open_time_ms=anchor_open_time_ms,
    )
    base = _cache_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key)
    tmp = path.with_suffix(".json.tmp")
    body = {
        "anchor_open_time_ms": anchor_open_time_ms,
        "symbol": request.symbol,
        "interval": request.interval,
        "eff_limit": eff_limit,
        "segment_engine": settings.segment_engine,
        "rules_version": RULES_VERSION,
        "response": response.model_dump(mode="json"),
    }
    tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    _prune_cache_directory()


def _prune_cache_directory() -> None:
    max_keep = settings.analyze_disk_cache_max_files
    if max_keep <= 0:
        return
    base = _cache_dir()
    if not base.is_dir():
        return
    files = sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in files[max_keep:]:
        try:
            stale.unlink()
        except OSError:
            pass
