"""Paper trading engine with full order lifecycle, position management, and equity tracking."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from app.core.config import settings
from app.core.models import (
    PaperOrderFull,
    PaperPosition,
    Signal,
    SignalSide,
    TradingAccountSummary,
)

_lock = threading.Lock()


def _db_path() -> Path:
    raw = Path(settings.paper_orders_db_path).expanduser()
    return raw if raw.is_absolute() else Path.cwd() / raw


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pe_positions (
    position_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit_1 REAL,
    take_profit_2 REAL,
    trailing_stop REAL,
    peak_price REAL,
    trough_price REAL,
    margin_used REAL NOT NULL,
    leverage INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'open',
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    close_reason TEXT,
    realized_pnl REAL NOT NULL DEFAULT 0,
    signal_kind TEXT,
    reductions_done TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pe_pos_status ON pe_positions(status);
CREATE INDEX IF NOT EXISTS idx_pe_pos_symbol ON pe_positions(symbol);

CREATE TABLE IF NOT EXISTS pe_orders (
    order_id TEXT PRIMARY KEY,
    position_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL DEFAULT 'open',
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'filled',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pe_ord_pos ON pe_orders(position_id);
CREATE INDEX IF NOT EXISTS idx_pe_ord_time ON pe_orders(created_at DESC);

CREATE TABLE IF NOT EXISTS pe_equity_log (
    log_id TEXT PRIMARY KEY,
    equity REAL NOT NULL,
    balance REAL NOT NULL,
    unrealized_pnl REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pe_eq_time ON pe_equity_log(created_at DESC);

CREATE TABLE IF NOT EXISTS pe_trade_journal (
    position_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    signal_kind TEXT,
    signal_strength REAL,
    signal_idx INTEGER,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit_1 REAL,
    take_profit_2 REAL,
    risk_reward_ratio REAL,
    quantity REAL,
    analysis_snapshot TEXT NOT NULL DEFAULT '{}',
    exit_price REAL,
    exit_reason TEXT,
    realized_pnl REAL,
    r_multiple REAL,
    hold_seconds INTEGER,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    review_tags TEXT NOT NULL DEFAULT '',
    review_notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pe_tj_symbol ON pe_trade_journal(symbol);
CREATE INDEX IF NOT EXISTS idx_pe_tj_closed ON pe_trade_journal(closed_at DESC);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    for stmt in _SCHEMA.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)


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


class PaperEngine:
    """Stateless paper trading engine: all state lives in SQLite."""

    def __init__(
        self,
        initial_equity: float = 1000.0,
        leverage: int = 5,
        risk_fraction: float = 0.01,
        fee_rate: float = 0.0005,
        max_positions: int = 5,
        tp1_ratio: float = 0.5,
    ):
        self.initial_equity = initial_equity
        self.leverage = leverage
        self.risk_fraction = risk_fraction
        self.fee_rate = fee_rate
        self.max_positions = max_positions
        self.tp1_ratio = tp1_ratio

    def _ensure_initial_equity(self) -> None:
        with _locked_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM pe_equity_log LIMIT 1"
            ).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO pe_equity_log (log_id, equity, balance, reason, created_at) VALUES (?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        self.initial_equity,
                        self.initial_equity,
                        "initial_deposit",
                        datetime.now(tz=timezone.utc).isoformat(),
                    ),
                )

    def get_balance(self, conn: sqlite3.Connection) -> float:
        row = conn.execute(
            "SELECT balance FROM pe_equity_log ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return float(row["balance"]) if row else self.initial_equity

    def get_open_positions(self, conn: sqlite3.Connection) -> list[dict]:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM pe_positions WHERE status IN ('open','partial_closed') ORDER BY opened_at"
            ).fetchall()
        ]

    def get_open_position_for_symbol(self, conn: sqlite3.Connection, symbol: str) -> Optional[dict]:
        row = conn.execute(
            "SELECT * FROM pe_positions WHERE symbol=? AND status IN ('open','partial_closed') LIMIT 1",
            (symbol,),
        ).fetchone()
        return dict(row) if row else None

    def _log_equity(self, conn: sqlite3.Connection, balance: float, unrealized: float, reason: str) -> None:
        conn.execute(
            "INSERT INTO pe_equity_log (log_id, equity, balance, unrealized_pnl, reason, created_at) VALUES (?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                balance + unrealized,
                balance,
                unrealized,
                reason,
                datetime.now(tz=timezone.utc).isoformat(),
            ),
        )

    def _record_order(
        self, conn: sqlite3.Connection, *, position_id: str | None, symbol: str,
        side: str, order_type: str, quantity: float, price: float, reason: str,
    ) -> str:
        oid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO pe_orders (order_id, position_id, symbol, side, order_type, quantity, price, reason, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                oid, position_id, symbol, side, order_type, quantity, price,
                reason, datetime.now(tz=timezone.utc).isoformat(),
            ),
        )
        return oid

    def open_position_from_signal(
        self, signal: Signal, symbol: str, analysis_snapshot: dict[str, Any] | None = None,
    ) -> Optional[str]:
        """Open a position from a trading signal. Returns position_id or None."""
        self._ensure_initial_equity()

        if not signal.stop_loss or signal.stop_loss == signal.price:
            return None

        with _locked_conn() as conn:
            open_count = len(self.get_open_positions(conn))
            if open_count >= self.max_positions:
                return None

            balance = self.get_balance(conn)
            risk_usdt = balance * self.risk_fraction
            move = abs(signal.price - signal.stop_loss)
            if move <= 0:
                return None
            qty = risk_usdt / move
            notional = qty * signal.price
            margin = notional / self.leverage

            if margin > balance or qty <= 0:
                return None

            pid = str(uuid.uuid4())
            now = datetime.now(tz=timezone.utc).isoformat()
            import json as _json

            # Clamp TP1 to be between entry and TP2
            tp1 = signal.take_profit_1
            tp2 = signal.take_profit
            is_long = signal.side == SignalSide.BUY
            if tp1 is not None and tp2 is not None:
                if is_long:
                    tp1 = min(tp1, tp2)
                else:
                    tp1 = max(tp1, tp2)

            # Deduct margin from balance
            new_balance = balance - margin
            self._log_equity(conn, new_balance, 0, f"open_{symbol}")

            conn.execute(
                """INSERT INTO pe_positions
                (position_id, symbol, side, entry_price, quantity, stop_loss,
                 take_profit_1, take_profit_2, margin_used, leverage, status,
                 opened_at, signal_kind, peak_price, trough_price, reductions_done)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pid, symbol, "LONG" if signal.side == SignalSide.BUY else "SHORT",
                    signal.price, qty, signal.stop_loss,
                    tp1, tp2,
                    margin, self.leverage, "open", now, signal.kind,
                    signal.price, signal.price, "",
                ),
            )
            self._record_order(
                conn, position_id=pid, symbol=symbol,
                side="BUY" if signal.side == SignalSide.BUY else "SELL",
                order_type="open", quantity=qty, price=signal.price,
                reason=f"signal:{signal.kind}",
            )
            # Write trade journal entry
            rr = getattr(signal, "risk_reward_ratio", None)
            conn.execute(
                """INSERT INTO pe_trade_journal
                (position_id, symbol, side, signal_kind, signal_strength, signal_idx,
                 entry_price, stop_loss, take_profit_1, take_profit_2,
                 risk_reward_ratio, quantity, analysis_snapshot, opened_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pid, symbol,
                    "LONG" if signal.side == SignalSide.BUY else "SHORT",
                    signal.kind, signal.strength, signal.idx,
                    signal.price, signal.stop_loss,
                    tp1, tp2,
                    rr, qty,
                    _json.dumps(analysis_snapshot or {}, ensure_ascii=False),
                    now,
                ),
            )
            return pid

    def check_sl_tp(self, symbol: str, high: float, low: float, close: float) -> list[str]:
        """Check SL/TP triggers for a symbol. Returns list of closed position_ids."""
        closed = []
        with _locked_conn() as conn:
            pos = self.get_open_position_for_symbol(conn, symbol)
            if not pos:
                return closed

            pid = pos["position_id"]
            side = pos["side"]
            sl = pos["stop_loss"] or pos["trailing_stop"] or 0
            tp1 = pos["take_profit_1"]
            tp2 = pos["take_profit_2"]
            entry = pos["entry_price"]
            qty = pos["quantity"]

            # Check stop loss
            if side == "LONG" and low <= sl:
                self._close_position(conn, pid, sl, "stop_loss")
                closed.append(pid)
                return closed
            if side == "SHORT" and high >= sl:
                self._close_position(conn, pid, sl, "stop_loss")
                closed.append(pid)
                return closed

            # Check TP1 (partial close)
            if tp1 and pos["status"] == "open":
                hit = (side == "LONG" and high >= tp1) or (side == "SHORT" and low <= tp1)
                if hit:
                    close_qty = qty * self.tp1_ratio
                    pnl = self._compute_pnl(side, entry, tp1, close_qty)
                    remaining = qty - close_qty
                    margin_remaining = pos["margin_used"] * (remaining / qty) if qty > 0 else 0
                    balance = self.get_balance(conn) + pos["margin_used"] * (close_qty / qty) + pnl
                    new_sl = entry  # Move SL to breakeven
                    conn.execute(
                        """UPDATE pe_positions SET quantity=?, margin_used=?, status='partial_closed',
                           stop_loss=?, realized_pnl=realized_pnl+?, peak_price=?, trough_price=?
                           WHERE position_id=?""",
                        (remaining, margin_remaining, new_sl, pnl, max(pos["peak_price"] or entry, high if side == "LONG" else entry),
                         min(pos["trough_price"] or entry, low if side == "SHORT" else entry), pid),
                    )
                    self._record_order(
                        conn, position_id=pid, symbol=symbol,
                        side="SELL" if side == "LONG" else "BUY",
                        order_type="partial_close", quantity=close_qty, price=tp1,
                        reason="take_profit_1",
                    )
                    self._log_equity(conn, balance, 0, f"tp1_{symbol}")
                    return closed

            # Check TP2 (full close)
            if tp2:
                hit = (side == "LONG" and high >= tp2) or (side == "SHORT" and low <= tp2)
                if hit:
                    self._close_position(conn, pid, tp2, "take_profit_2")
                    closed.append(pid)
                    return closed

            # Update peak/trough for trailing stop
            if side == "LONG":
                conn.execute(
                    "UPDATE pe_positions SET peak_price=MAX(COALESCE(peak_price,0),?) WHERE position_id=?",
                    (high, pid),
                )
            else:
                conn.execute(
                    "UPDATE pe_positions SET trough_price=MIN(COALESCE(trough_price,999999),?) WHERE position_id=?",
                    (low, pid),
                )

        return closed

    def reduce_position(self, position_id: str, fraction: float, price: float) -> float:
        """Partially close a position. Returns realized P&L from this reduction."""
        with _locked_conn() as conn:
            row = conn.execute("SELECT * FROM pe_positions WHERE position_id=? AND status IN ('open','partial_closed')", (position_id,)).fetchone()
            if not row:
                return 0.0
            pos = dict(row)
            side = pos["side"]
            entry = pos["entry_price"]
            qty = pos["quantity"]
            margin = pos["margin_used"]

            reduce_qty = qty * fraction
            if reduce_qty < 1e-8:
                return 0.0

            remaining = qty - reduce_qty
            pnl = self._compute_pnl(side, entry, price, reduce_qty)

            if remaining < 1e-8:
                # Full close
                self._close_position(conn, position_id, price, "auto_reduce_full")
                return pnl

            # Update position
            margin_remaining = margin * (remaining / qty)
            new_status = "partial_closed"
            conn.execute(
                """UPDATE pe_positions SET quantity=?, margin_used=?, status=?,
                   realized_pnl=realized_pnl+? WHERE position_id=?""",
                (remaining, margin_remaining, new_status, pnl, position_id),
            )
            # Return margin + PnL to balance
            balance = self.get_balance(conn) + margin * fraction + pnl
            self._record_order(
                conn, position_id=position_id, symbol=pos["symbol"],
                side="SELL" if side == "LONG" else "BUY",
                order_type="reduce", quantity=reduce_qty, price=price,
                reason=f"auto_reduce_{fraction:.0%}",
            )
            self._log_equity(conn, balance, 0, f"reduce_{pos['symbol']}")
            return pnl

    def mark_reduction_done(self, position_id: str, threshold: float) -> None:
        """Record that a reduction threshold has been executed for a position."""
        import json as _json
        with _locked_conn() as conn:
            row = conn.execute(
                "SELECT reductions_done FROM pe_positions WHERE position_id=?", (position_id,)
            ).fetchone()
            if not row:
                return
            existing = _json.loads(row["reductions_done"]) if row["reductions_done"] else []
            val = str(threshold)
            if val not in existing:
                existing.append(val)
            conn.execute(
                "UPDATE pe_positions SET reductions_done=? WHERE position_id=?",
                (_json.dumps(existing), position_id),
            )

    def update_trailing_stop(self, position_id: str, new_stop: float) -> None:
        with _locked_conn() as conn:
            conn.execute(
                "UPDATE pe_positions SET trailing_stop=? WHERE position_id=?",
                (new_stop, position_id),
            )
            # Update stop_loss to use trailing if tighter
            conn.execute(
                """UPDATE pe_positions SET stop_loss=(
                    CASE WHEN side='LONG' THEN MAX(stop_loss, ?)
                         ELSE MIN(stop_loss, ?) END
                ) WHERE position_id=?""",
                (new_stop, new_stop, position_id),
            )

    def _close_position(self, conn: sqlite3.Connection, pid: str, exit_price: float, reason: str) -> float:
        pos = dict(conn.execute("SELECT * FROM pe_positions WHERE position_id=?", (pid,)).fetchone())
        side = pos["side"]
        qty = pos["quantity"]
        entry = pos["entry_price"]
        margin = pos["margin_used"]

        pnl = self._compute_pnl(side, entry, exit_price, qty)
        balance = self.get_balance(conn) + margin + pnl
        now = datetime.now(tz=timezone.utc).isoformat()

        conn.execute(
            """UPDATE pe_positions SET status='closed', closed_at=?, close_reason=?,
               realized_pnl=realized_pnl+? WHERE position_id=?""",
            (now, reason, pnl, pid),
        )
        self._record_order(
            conn, position_id=pid, symbol=pos["symbol"],
            side="SELL" if side == "LONG" else "BUY",
            order_type="close", quantity=qty, price=exit_price,
            reason=reason,
        )
        self._log_equity(conn, balance, 0, f"close_{reason}_{pos['symbol']}")

        # Update trade journal with exit data
        risk = abs(entry - pos["stop_loss"]) if pos["stop_loss"] else 0
        r_mult = ((exit_price - entry) / risk if side == "LONG" else (entry - exit_price) / risk) if risk > 0 else 0
        opened = pos.get("opened_at", now)
        try:
            from datetime import datetime as _dt
            hold = int((_dt.fromisoformat(now) - _dt.fromisoformat(opened)).total_seconds())
        except (ValueError, TypeError):
            hold = 0
        conn.execute(
            """UPDATE pe_trade_journal SET exit_price=?, exit_reason=?, realized_pnl=?,
               r_multiple=?, hold_seconds=?, closed_at=? WHERE position_id=?""",
            (exit_price, reason, pnl, r_mult, hold, now, pid),
        )
        return pnl

    def close_position(self, position_id: str, exit_price: float, reason: str = "manual") -> float:
        with _locked_conn() as conn:
            return self._close_position(conn, position_id, exit_price, reason)

    def _compute_pnl(self, side: str, entry: float, exit_price: float, qty: float) -> float:
        fee = qty * (entry + exit_price) * self.fee_rate
        if side == "LONG":
            return qty * (exit_price - entry) - fee
        else:
            return qty * (entry - exit_price) - fee

    def get_account_summary(self, prices: dict[str, float] | None = None) -> TradingAccountSummary:
        self._ensure_initial_equity()
        with _locked_conn() as conn:
            balance = self.get_balance(conn)
            positions = self.get_open_positions(conn)
            unrealized = sum(
                self._compute_pnl(p["side"], p["entry_price"],
                                  (prices or {}).get(p["symbol"], p["entry_price"]),
                                  p["quantity"])
                for p in positions
            )
            total_realized = sum(
                float(r[0] or 0) for r in conn.execute("SELECT SUM(realized_pnl) FROM pe_positions WHERE status='closed'").fetchall()
            )
            today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
            daily_pnl = sum(
                float(r[0] or 0) for r in conn.execute(
                    "SELECT SUM(realized_pnl) FROM pe_positions WHERE status='closed' AND closed_at LIKE ?",
                    (f"{today}%",),
                ).fetchall()
            )
            daily_trades = int(
                conn.execute(
                    "SELECT COUNT(*) FROM pe_orders WHERE order_type='close' AND created_at LIKE ?",
                    (f"{today}%",),
                ).fetchone()[0]
            )
            margin_locked = sum(p["margin_used"] for p in positions)
            return TradingAccountSummary(
                initial_equity=self.initial_equity,
                current_equity=balance + margin_locked + unrealized,
                available_balance=balance,
                unrealized_pnl=unrealized,
                open_positions=len(positions),
                total_realized_pnl=total_realized,
                daily_pnl=daily_pnl,
                daily_trades=daily_trades,
            )

    def get_positions(self, status: Optional[str] = None) -> list[PaperPosition]:
        with _locked_conn() as conn:
            if status:
                rows = conn.execute("SELECT * FROM pe_positions WHERE status=? ORDER BY opened_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM pe_positions ORDER BY opened_at DESC").fetchall()
            return [PaperPosition(**dict(r)) for r in rows]

    def get_orders(self, limit: int = 100) -> list[PaperOrderFull]:
        with _locked_conn() as conn:
            rows = conn.execute("SELECT * FROM pe_orders ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [PaperOrderFull(**dict(r)) for r in rows]

    def get_equity_history(self, limit: int = 200) -> list[dict[str, Any]]:
        with _locked_conn() as conn:
            rows = conn.execute("SELECT * FROM pe_equity_log ORDER BY created_at ASC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_trade_journal(self, limit: int = 50, symbol: str | None = None) -> list[dict[str, Any]]:
        with _locked_conn() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM pe_trade_journal WHERE symbol=? ORDER BY opened_at DESC LIMIT ?",
                    (symbol, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM pe_trade_journal ORDER BY opened_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def update_trade_review(self, position_id: str, tags: str = "", notes: str = "") -> bool:
        with _locked_conn() as conn:
            cur = conn.execute(
                "UPDATE pe_trade_journal SET review_tags=?, review_notes=? WHERE position_id=?",
                (tags, notes, position_id),
            )
            return cur.rowcount > 0
