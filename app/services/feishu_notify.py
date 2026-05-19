"""Feishu (Lark) notification client for card messages."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

_BASE_URL = "https://open.feishu.cn/open-apis"


async def get_tenant_token(app_id: str, app_secret: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{_BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu auth failed: {data}")
        return data["tenant_access_token"]


async def send_card(token: str, chat_id: str, card: dict[str, Any]) -> str:
    body = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_BASE_URL}/im/v1/messages?receive_id_type=chat_id",
            json=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu send failed: {data}")
        return data.get("data", {}).get("message_id", "")
