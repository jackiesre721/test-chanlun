"""纸上撮合记账（进程内）。不涉及交易所私有签名。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

_lock = threading.Lock()
_orders: list[dict[str, Any]] = []


def record_paper_order(*, symbol: str, side: str, quantity: float, note: str) -> str:
    oid = str(uuid.uuid4())
    row = {
        "order_id": oid,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "note": note,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    with _lock:
        _orders.insert(0, row)
        del _orders[500:]
    return oid


def recent_orders(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        return list(_orders[:limit])
