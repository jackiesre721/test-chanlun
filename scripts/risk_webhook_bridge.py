#!/usr/bin/env python3
"""Webhook 桥接服务 — 将外部事件转发给 OpenClaw 触发风险分析。

启动:
  python3 scripts/risk_webhook_bridge.py

端点:
  POST /hooks/crypto-twitter   — X/Twitter 事件
  POST /hooks/crypto-news      — 新闻事件
  POST /hooks/crypto-onchain   — 链上事件
  POST /hooks/crypto-macro     — 宏观数据
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PORT = 18800
FEISHU_CHAT = "oc_37013a6979c00bd481d8955496578783"
OPENCLAW_BIN = "/opt/homebrew/bin/openclaw"
DEDUP_TTL = 60  # seconds

# ---------------------------------------------------------------------------
# Dedup cache
# ---------------------------------------------------------------------------

_dedup: dict[str, float] = {}


def _dedup_key(endpoint: str, payload: dict) -> str:
    raw = f"{endpoint}:{json.dumps(payload, sort_keys=True, ensure_ascii=False)}"
    return hashlib.md5(raw.encode()).hexdigest()


def _is_duplicate(key: str) -> bool:
    now = time.time()
    # cleanup expired
    expired = [k for k, t in _dedup.items() if now - t > DEDUP_TTL]
    for k in expired:
        del _dedup[k]
    if key in _dedup:
        return True
    _dedup[key] = now
    return False


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_prompt(source_type: str, payload: dict) -> str:
    if source_type == "twitter":
        author = payload.get("author", "unknown")
        text = payload.get("text", "")
        url = payload.get("url", "")
        return (
            f"收到 X/Twitter 加密货币相关事件，请立即进行风险分析：\n"
            f"作者: @{author}\n内容: {text}\n链接: {url}\n\n"
            f"读取 ~/.openclaw/workspace/crypto-risk-state.json 获取上次风险等级，"
            f"交叉验证后输出新评级。仅在等级变化时推送飞书卡片。"
        )

    if source_type == "news":
        title = payload.get("title", "")
        source = payload.get("source", "")
        summary = payload.get("summary", "")
        return (
            f"收到加密货币相关新闻，请立即进行风险分析：\n"
            f"标题: {title}\n来源: {source}\n摘要: {summary}\n\n"
            f"读取 ~/.openclaw/workspace/crypto-risk-state.json 获取上次风险等级，"
            f"交叉验证后输出新评级。仅在等级变化时推送飞书卡片。"
        )

    if source_type == "onchain":
        event_type = payload.get("type", "unknown")
        chain = payload.get("chain", "unknown")
        detail = payload.get("detail", "")
        return (
            f"收到链上监控事件，请立即进行风险分析：\n"
            f"事件类型: {event_type}\n链: {chain}\n详情: {detail}\n\n"
            f"读取 ~/.openclaw/workspace/crypto-risk-state.json 获取上次风险等级，"
            f"交叉验证后输出新评级。链上安全事件（黑客/Rug Pull）直接 RED。"
            f"仅在等级变化时推送飞书卡片。"
        )

    if source_type == "macro":
        indicator = payload.get("indicator", "unknown")
        value = payload.get("value", "")
        expected = payload.get("expected", "")
        return (
            f"收到宏观经济数据发布，请立即进行风险分析：\n"
            f"指标: {indicator}\n实际值: {value}\n预期值: {expected}\n\n"
            f"读取 ~/.openclaw/workspace/crypto-risk-state.json 获取上次风险等级，"
            f"交叉验证后输出新评级。仅在等级变化时推送飞书卡片。"
        )

    return f"收到未知类型事件，请进行风险分析：{json.dumps(payload, ensure_ascii=False)}"


# ---------------------------------------------------------------------------
# OpenClaw invocation
# ---------------------------------------------------------------------------


def _invoke_openclaw(prompt: str) -> dict:
    try:
        result = subprocess.run(
            [
                OPENCLAW_BIN, "system", "event",
                "--text", prompt,
                "--mode", "now",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "error": "timeout"}
    except Exception as e:
        return {"exit_code": -1, "error": str(e)}


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Crypto Risk Webhook Bridge", version="1.0")


@app.post("/hooks/crypto-twitter")
async def hook_twitter(request: Request):
    payload = await request.json()
    key = _dedup_key("twitter", payload)
    if _is_duplicate(key):
        return JSONResponse({"status": "deduplicated"}, status_code=200)
    prompt = _build_prompt("twitter", payload)
    result = _invoke_openclaw(prompt)
    return JSONResponse({"status": "triggered", "result": result})


@app.post("/hooks/crypto-news")
async def hook_news(request: Request):
    payload = await request.json()
    key = _dedup_key("news", payload)
    if _is_duplicate(key):
        return JSONResponse({"status": "deduplicated"}, status_code=200)
    prompt = _build_prompt("news", payload)
    result = _invoke_openclaw(prompt)
    return JSONResponse({"status": "triggered", "result": result})


@app.post("/hooks/crypto-onchain")
async def hook_onchain(request: Request):
    payload = await request.json()
    key = _dedup_key("onchain", payload)
    if _is_duplicate(key):
        return JSONResponse({"status": "deduplicated"}, status_code=200)
    prompt = _build_prompt("onchain", payload)
    result = _invoke_openclaw(prompt)
    return JSONResponse({"status": "triggered", "result": result})


@app.post("/hooks/crypto-macro")
async def hook_macro(request: Request):
    payload = await request.json()
    key = _dedup_key("macro", payload)
    if _is_duplicate(key):
        return JSONResponse({"status": "deduplicated"}, status_code=200)
    prompt = _build_prompt("macro", payload)
    result = _invoke_openclaw(prompt)
    return JSONResponse({"status": "triggered", "result": result})


@app.get("/health")
async def health():
    return {"status": "ok", "dedup_cache_size": len(_dedup)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
