#!/usr/bin/env python3
"""缠论每日信号推送 + 交易日志。

用法:
  python scripts/daily_signal.py push [--force] [--dry-run]   # 推送今日信号（默认）
  python scripts/daily_signal.py log [--last N]               # 查看交易日志
  python scripts/daily_signal.py update <id> [选项]           # 更新交易结果
  python scripts/daily_signal.py review                       # 推送复盘卡片到飞书

update 选项:
  --status filled|closed|sl_hit|tp_hit|cancelled
  --entry <实际入场价>
  --exit <实际出场价>
  --pnl <盈亏 USDT>
  --notes <备注>
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import ssl
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_dotenv = Path(__file__).parent / ".env"
_cfg: dict[str, str] = {}

if _dotenv.exists():
    for line in _dotenv.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            _cfg[k.strip()] = v.strip().strip("\"'")

BACKEND_URL = os.getenv("SIGNAL_BACKEND_URL", _cfg.get("BACKEND_URL", "http://localhost:8000"))
FEISHU_APP_ID = os.getenv("SIGNAL_FEISHU_APP_ID", _cfg.get("FEISHU_APP_ID", ""))
FEISHU_APP_SECRET = os.getenv("SIGNAL_FEISHU_APP_SECRET", _cfg.get("FEISHU_APP_SECRET", ""))
FEISHU_CHAT_ID = os.getenv("SIGNAL_FEISHU_CHAT_ID", _cfg.get("FEISHU_CHAT_ID", ""))

SYMBOL = os.getenv("SIGNAL_SYMBOL", _cfg.get("SIGNAL_SYMBOL", "SOLUSDT"))
INTERVAL = os.getenv("SIGNAL_INTERVAL", _cfg.get("SIGNAL_INTERVAL", "60"))
EQUITY = float(os.getenv("SIGNAL_EQUITY", _cfg.get("SIGNAL_EQUITY", "200")))
LEVERAGE = int(os.getenv("SIGNAL_LEVERAGE", _cfg.get("SIGNAL_LEVERAGE", "5")))
RISK_FRAC = float(os.getenv("SIGNAL_RISK_FRAC", _cfg.get("SIGNAL_RISK_FRAC", "0.02")))
MAINT_RATE = float(os.getenv("SIGNAL_MAINT_RATE", _cfg.get("SIGNAL_MAINT_RATE", "0.004")))
TRADING_START = int(os.getenv("SIGNAL_TRADING_START", _cfg.get("SIGNAL_TRADING_START", "7")))
TRADING_END = int(os.getenv("SIGNAL_TRADING_END", _cfg.get("SIGNAL_TRADING_END", "19")))

_CST = timezone(timedelta(hours=8))
_DB_DIR = Path(__file__).parent.parent / ".cache" / "chanlan"
_DB_PATH = _DB_DIR / "trade_journal.sqlite"

# ---------------------------------------------------------------------------
# Trade Journal (SQLite)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT    NOT NULL,
    symbol       TEXT    NOT NULL,
    side         TEXT    NOT NULL,
    signal_type  TEXT    NOT NULL,
    signal_time  TEXT,
    entry_price  REAL,
    stop_loss    REAL,
    take_profit_1 REAL,
    take_profit_2 REAL,
    quantity     REAL,
    margin       REAL,
    risk_usdt    REAL,
    status       TEXT    NOT NULL DEFAULT 'pending',
    actual_entry REAL,
    actual_exit  REAL,
    pnl_usdt     REAL,
    pnl_pct      REAL,
    notes        TEXT,
    feishu_msg_id TEXT,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT
);
"""


def _db() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def journal_save(sig: dict, pos: dict, msg_id: str = "") -> int:
    now = datetime.now(_CST).strftime("%Y-%m-%d %H:%M:%S")
    kind_map = {
        "first": "一类", "second_class": "二类",
        "third": "三类", "class_second": "类二",
        "class_third": "类三", "second_ext": "二类延伸",
    }
    side = sig.get("side", "BUY")
    kind_cn = kind_map.get(sig.get("kind", ""), sig.get("kind", ""))
    signal_type = f"{kind_cn}{'买点' if side == 'BUY' else '卖点'}"

    conn = _db()
    cur = conn.execute(
        """INSERT INTO trades
           (date, symbol, side, signal_type, signal_time,
            entry_price, stop_loss, take_profit_1, take_profit_2,
            quantity, margin, risk_usdt, status, feishu_msg_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            now[:10], SYMBOL, side, signal_type, sig.get("time", ""),
            round(sig.get("price", 0) or 0, 2),
            round(sig.get("stop_loss", 0) or 0, 2),
            round(sig.get("take_profit_1", 0) or 0, 2),
            round(sig.get("take_profit_2", 0) or 0, 2),
            pos.get("qty", 0), pos.get("margin", 0), pos.get("risk_usdt", 0),
            "pending", msg_id, now,
        ),
    )
    trade_id = cur.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def journal_update(trade_id: int, **kwargs) -> bool:
    now = datetime.now(_CST).strftime("%Y-%m-%d %H:%M:%S")
    sets = []
    vals = []
    for k in ("status", "actual_entry", "actual_exit", "pnl_usdt", "pnl_pct", "notes"):
        if k in kwargs and kwargs[k] is not None:
            sets.append(f"{k} = ?")
            vals.append(kwargs[k])
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(now)
    vals.append(trade_id)

    conn = _db()
    conn.execute(f"UPDATE trades SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return True


def journal_list(last_n: int = 20) -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (last_n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def journal_get(trade_id: int) -> dict | None:
    conn = _db()
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

_ctx = ssl.create_default_context()


def _post(url: str, body: dict, headers: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, context=_ctx) as resp:
        return json.loads(resp.read())


def _get(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, context=_ctx) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Feishu
# ---------------------------------------------------------------------------

def feishu_token() -> str:
    resp = _post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        {"Content-Type": "application/json"},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"Feishu auth failed: {resp}")
    return resp["tenant_access_token"]


def feishu_send(token: str, card: dict) -> str:
    body = {
        "receive_id": FEISHU_CHAT_ID,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }
    resp = _post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        body,
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"Feishu send failed: {resp}")
    return resp.get("data", {}).get("message_id", "")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def fetch_signal() -> dict:
    resp = _post(
        f"{BACKEND_URL}/analyze",
        {"market": "crypto", "symbol": SYMBOL, "interval": INTERVAL, "limit": 500},
        {"Content-Type": "application/json"},
    )
    if not resp.get("success"):
        raise RuntimeError(f"Analyze failed: {resp}")
    return resp


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------

def calc_position(entry: float, sl: float) -> dict:
    risk_usdt = EQUITY * RISK_FRAC
    move = abs(entry - sl)
    if move <= 0:
        return {}
    qty = risk_usdt / move
    notional = qty * entry
    margin = notional / LEVERAGE
    is_long = entry > sl
    if is_long:
        liq = entry * (1 - 1 / LEVERAGE + MAINT_RATE)
    else:
        liq = entry * (1 + 1 / LEVERAGE - MAINT_RATE)
    return {
        "qty": round(qty, 4),
        "notional": round(notional, 2),
        "margin": round(margin, 2),
        "liq": round(liq, 2),
        "risk_usdt": round(risk_usdt, 2),
    }


# ---------------------------------------------------------------------------
# Card builder
# ---------------------------------------------------------------------------

SIDE_EMOJI = {"BUY": "✅", "SELL": "⚠️"}
SIDE_CN = {"BUY": "做多 LONG", "SELL": "做空 SHORT"}
SIDE_COLOR = {"BUY": "green", "SELL": "red"}
STATUS_CN = {
    "pending": "⏳ 等待入场", "filled": "📐 已入场",
    "closed": "💰 已平仓", "sl_hit": "🔴 止损",
    "tp_hit": "🟢 止盈", "cancelled": "❌ 已取消",
}


def _col_set(bg: str, cols: list[dict]) -> dict:
    return {
        "tag": "column_set",
        "flex_mode": "bisect",
        "background_style": bg,
        "columns": [
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [c]}
            for c in cols
        ],
    }


def _col_md(text: str) -> dict:
    return {"tag": "markdown", "content": text}


def build_signal_card(analysis: dict, sig: dict, pos: dict, trade_id: int) -> dict:
    price = analysis.get("current_price", 0)
    side = sig.get("side", "BUY")
    kind_map = {
        "first": "一类", "second_class": "二类",
        "third": "三类", "class_second": "类二",
        "class_third": "类三", "second_ext": "二类延伸",
    }
    kind_cn = kind_map.get(sig.get("kind", ""), sig.get("kind", ""))
    kind_label = f"{kind_cn}买点" if side == "BUY" else f"{kind_cn}卖点"
    af = analysis.get("action_focus", {})
    pivot = af.get("primary_pivot", {})
    pivot_rel = {"above": "中枢上方", "below": "中枢下方",
                 "inside": "中枢内部", "none": "无"}.get(
        pivot.get("relation", "none"), pivot.get("relation", ""))
    now = datetime.now(_CST).strftime("%Y-%m-%d %H:%M")

    sl = round(sig.get("stop_loss", 0) or 0, 2)
    tp1 = round(sig.get("take_profit_1", 0) or 0, 2)
    tp2 = round(sig.get("take_profit_2", 0) or 0, 2)
    entry = round(sig.get("price", 0) or 0, 2)

    sl_pct = f"{(sl - entry) / entry * 100:+.2f}%" if entry else ""
    tp1_pct = f"{(tp1 - entry) / entry * 100:+.2f}%" if entry else ""
    tp2_pct = f"{(tp2 - entry) / entry * 100:+.2f}%" if entry else ""

    rr1 = abs(tp1 - entry) / abs(entry - sl) if entry and sl and tp1 else 0
    rr2 = abs(tp2 - entry) / abs(entry - sl) if entry and sl and tp2 else 0

    color = SIDE_COLOR.get(side, "turquoise")

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text",
                      "content": f"#{trade_id} {SYMBOL} {side} | {kind_label}"},
            "template": color,
            "subtitle": {"tag": "plain_text",
                         "content": f"{now} | 信号时间 {sig.get('time','')} | {INTERVAL}周期"},
        },
        "elements": [
            _col_set("default", [
                _col_md(f"**当前价**\n{price}"),
                _col_md(f"**方向**\n{SIDE_EMOJI.get(side,'')} {SIDE_CN.get(side,side)}"),
                _col_md(f"**信号**\n{kind_cn}"),
                _col_md(f"**位置**\n{pivot_rel}"),
            ]),
            {"tag": "hr"},
            _col_set("default", [
                _col_md(f"**限价{'买入' if side=='BUY' else '卖出'}**\n{entry}"),
                _col_md(f"**止损 SL**\n{sl} ({sl_pct})"),
                _col_md(f"**止盈 TP1**\n{tp1} ({tp1_pct})"),
                _col_md(f"**止盈 TP2**\n{tp2} ({tp2_pct})"),
            ]),
            {"tag": "hr"},
            _col_set("light_blue", [
                _col_md(f"**本金**\n{EQUITY} USDT"),
                _col_md(f"**杠杆**\n{LEVERAGE}x 固定"),
                _col_md(f"**下单量**\n{pos.get('qty','')} {SYMBOL.replace('USDT','')}"),
                _col_md(f"**保证金**\n{pos.get('margin','')} USDT"),
                _col_md(f"**最大亏损**\n{pos.get('risk_usdt','')} USDT ({RISK_FRAC*100:.0f}%)"),
                _col_md(f"**R:R**\nTP1 1:{rr1:.1f} | TP2 1:{rr2:.1f}"),
            ]),
            {"tag": "hr"},
            {
                "tag": "markdown",
                "content": (
                    f"**操作步骤**\n"
                    f"1. 限价挂单 **{entry}** {'买入' if side=='BUY' else '卖出'}\n"
                    f"2. 成交后挂 OCO: 止损 **{sl}** / 止盈 **{tp1}**\n"
                    f"3. 每天 **最多1单**，没到价位就不做\n"
                    f"4. 交易时段 **{TRADING_START:02d}:00 - {TRADING_END:02d}:00**"
                ),
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text",
                     "content": f"交易记录 #{trade_id} | Binance USD-M | 缠论引擎 v18 | 仅供参考"},
                ],
            },
        ],
    }


def build_review_card(trades: list[dict]) -> dict:
    now = datetime.now(_CST).strftime("%Y-%m-%d %H:%M")
    total_pnl = sum(t.get("pnl_usdt", 0) or 0 for t in trades)
    closed = [t for t in trades if t["status"] in ("closed", "sl_hit", "tp_hit")]
    wins = [t for t in closed if (t.get("pnl_usdt", 0) or 0) > 0]
    win_rate = f"{len(wins)/len(closed)*100:.0f}%" if closed else "—"

    # Recent trades detail
    detail_lines = []
    for t in trades[:10]:
        s = STATUS_CN.get(t["status"], t["status"])
        pnl = f"{t['pnl_usdt']:+.2f}U" if t.get("pnl_usdt") is not None else "—"
        detail_lines.append(
            f"#{t['id']} {t['date']} {t['side']} {t['signal_type']} "
            f"@ {t['entry_price']} | {s} | {pnl}"
        )
    detail_text = "\n".join(detail_lines) if detail_lines else "暂无记录"

    equity_now = EQUITY + total_pnl

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "复盘报告 | 交易日志汇总"},
            "template": "blue",
            "subtitle": {"tag": "plain_text", "content": f"生成时间 {now}"},
        },
        "elements": [
            _col_set("indigo", [
                _col_md(f"**总交易**\n{len(trades)} 笔"),
                _col_md(f"**已平仓**\n{len(closed)} 笔"),
                _col_md(f"**胜率**\n{win_rate}"),
                _col_md(f"**累计盈亏**\n{total_pnl:+.2f} USDT"),
            ]),
            {"tag": "hr"},
            _col_set("default", [
                _col_md(f"**初始本金**\n{EQUITY} USDT"),
                _col_md(f"**当前净值**\n{equity_now:.2f} USDT"),
                _col_md(f"**收益率**\n{total_pnl/EQUITY*100:+.2f}%"),
                _col_md(f"**杠杆**\n{LEVERAGE}x"),
            ]),
            {"tag": "hr"},
            {
                "tag": "markdown",
                "content": f"**最近交易明细**\n{detail_text}",
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text",
                     "content": "缠论引擎 v18 | 仅供参考"},
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_push(args) -> None:
    now = datetime.now(_CST)
    if not args.force and not (TRADING_START <= now.hour < TRADING_END):
        print(f"当前 {now.strftime('%H:%M')} 不在交易时段 {TRADING_START}:00-{TRADING_END}:00，跳过。用 --force 强制执行。")
        sys.exit(0)

    missing = [k for k, v in [("FEISHU_APP_ID", FEISHU_APP_ID),
                               ("FEISHU_APP_SECRET", FEISHU_APP_SECRET),
                               ("FEISHU_CHAT_ID", FEISHU_CHAT_ID)] if not v]
    if missing and not args.dry_run:
        print(f"缺少配置: {', '.join(missing)}。请编辑 scripts/.env")
        sys.exit(1)

    print(f"正在分析 {SYMBOL} {INTERVAL}...")
    analysis = fetch_signal()
    af = analysis.get("action_focus", {})
    sig = af.get("recent_signal")

    if not sig:
        print("当前无有效信号，跳过推送。")
        sys.exit(0)

    print(f"信号: {sig['side']} {sig['kind']} @ {sig['price']}")

    sl = sig.get("stop_loss")
    if not sl:
        print("信号无止损价，跳过。")
        sys.exit(0)

    entry = sig["price"]
    pos = calc_position(entry, sl)

    # Save to journal first
    trade_id = journal_save(sig, pos)

    card = build_signal_card(analysis, sig, pos, trade_id)

    if args.dry_run:
        print(f"\n交易记录 #{trade_id} 已保存到日志 (pending)")
        print("\n--- DRY RUN: Card JSON ---\n")
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return

    print("获取飞书 token...")
    token = feishu_token()
    print("发送飞书卡片...")
    msg_id = feishu_send(token, card)

    # Update journal with feishu msg id
    journal_update(trade_id, notes=f"feishu_msg_id={msg_id}")
    print(f"发送成功! 记录 #{trade_id}, message_id={msg_id}")


def cmd_log(args) -> None:
    trades = journal_list(args.last)
    if not trades:
        print("暂无交易记录。")
        return

    print(f"{'ID':>4} {'日期':>12} {'品种':>10} {'方向':>5} {'信号':>8} "
          f"{'入场':>9} {'止损':>9} {'状态':>10} {'盈亏':>10}")
    print("-" * 90)
    for t in trades:
        pnl = f"{t['pnl_usdt']:+.2f}U" if t.get("pnl_usdt") is not None else "—"
        status = STATUS_CN.get(t["status"], t["status"])
        print(f"{t['id']:>4} {t['date']:>12} {t['symbol']:>10} {t['side']:>5} "
              f"{t['signal_type']:>8} {t['entry_price']:>9.2f} {t['stop_loss']:>9.2f} "
              f"{status:>10} {pnl:>10}")


def cmd_update(args) -> None:
    trade = journal_get(args.trade_id)
    if not trade:
        print(f"交易记录 #{args.trade_id} 不存在。")
        sys.exit(1)

    kwargs = {}
    if args.status:
        kwargs["status"] = args.status
    if args.entry is not None:
        kwargs["actual_entry"] = args.entry
    if args.exit is not None:
        kwargs["actual_exit"] = args.exit
    if args.pnl is not None:
        kwargs["pnl_usdt"] = args.pnl
        if trade["entry_price"] and trade["entry_price"] > 0:
            kwargs["pnl_pct"] = round(args.pnl / (trade["margin"] or EQUITY) * 100, 2)
    if args.notes:
        kwargs["notes"] = args.notes

    if not kwargs:
        print("没有指定更新内容。使用 --status/--entry/--exit/--pnl/--notes")
        sys.exit(1)

    journal_update(args.trade_id, **kwargs)
    print(f"交易记录 #{args.trade_id} 已更新: {kwargs}")


def cmd_review(args) -> None:
    trades = journal_list(50)
    if not trades:
        print("暂无交易记录。")
        return

    if args.dry_run:
        print(json.dumps(build_review_card(trades), ensure_ascii=False, indent=2))
        return

    print("获取飞书 token...")
    token = feishu_token()
    card = build_review_card(trades)
    msg_id = feishu_send(token, card)
    print(f"复盘报告已发送! message_id={msg_id}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="缠论每日信号 → 飞书")
    sub = ap.add_subparsers(dest="command")

    # push (default)
    p_push = sub.add_parser("push", help="推送今日信号（默认）")
    p_push.add_argument("--force", action="store_true", help="忽略交易时段限制")
    p_push.add_argument("--dry-run", action="store_true", help="只打印不发送")

    # log
    p_log = sub.add_parser("log", help="查看交易日志")
    p_log.add_argument("--last", type=int, default=20, help="显示最近 N 条")

    # update
    p_update = sub.add_parser("update", help="更新交易结果")
    p_update.add_argument("trade_id", type=int, help="交易记录 ID")
    p_update.add_argument("--status", choices=["filled", "closed", "sl_hit", "tp_hit", "cancelled"])
    p_update.add_argument("--entry", type=float, help="实际入场价")
    p_update.add_argument("--exit", type=float, help="实际出场价")
    p_update.add_argument("--pnl", type=float, help="盈亏 USDT")
    p_update.add_argument("--notes", help="备注")

    # review
    p_review = sub.add_parser("review", help="推送复盘报告到飞书")
    p_review.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()

    # Default to push if no subcommand
    if not args.command:
        args.command = "push"
        args.force = False
        args.dry_run = False

    cmds = {
        "push": cmd_push,
        "log": cmd_log,
        "update": cmd_update,
        "review": cmd_review,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
