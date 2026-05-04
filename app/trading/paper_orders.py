"""纸上撮合记账：默认写入本地 SQLite，进程重启后仍可查询近期单据。"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings

_lock = threading.Lock()


def _db_path() -> Path:
    raw = Path(settings.paper_orders_db_path).expanduser()
    return raw if raw.is_absolute() else Path.cwd() / raw


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_orders (
            order_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_paper_orders_created ON paper_orders(created_at DESC)"
    )


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def _locked_conn() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = _connect()
        try:
            _ensure_schema(conn)
            yield conn
            conn.commit()
        finally:
            conn.close()


def _prune(conn: sqlite3.Connection) -> None:
    max_keep = settings.paper_orders_max_rows
    if max_keep <= 0:
        return
    row = conn.execute("SELECT COUNT(*) FROM paper_orders").fetchone()
    n = int(row[0]) if row else 0
    if n <= max_keep:
        return
    excess = n - max_keep
    conn.execute(
        """
        DELETE FROM paper_orders WHERE order_id IN (
            SELECT order_id FROM paper_orders ORDER BY created_at ASC LIMIT ?
        )
        """,
        (excess,),
    )


def record_paper_order(*, symbol: str, side: str, quantity: float, note: str) -> str:
    oid = str(uuid.uuid4())
    created = datetime.now(tz=timezone.utc).isoformat()
    with _locked_conn() as conn:
        conn.execute(
            """
            INSERT INTO paper_orders (order_id, symbol, side, quantity, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (oid, symbol, side, quantity, note, created),
        )
        _prune(conn)
    return oid


def recent_orders(limit: int = 50) -> list[dict[str, Any]]:
    capped = max(1, min(limit, 2000))
    with _locked_conn() as conn:
        rows = conn.execute(
            """
            SELECT order_id, symbol, side, quantity, note, created_at
            FROM paper_orders
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (capped,),
        ).fetchall()
    return [dict(r) for r in rows]
