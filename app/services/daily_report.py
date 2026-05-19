"""Daily trading report builder and Feishu card publisher."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.feishu_notify import get_tenant_token, send_card
from app.trading.paper_engine import PaperEngine

log = logging.getLogger(__name__)


def build_daily_report(engine: PaperEngine) -> dict[str, Any]:
    """Build a Feishu interactive card with daily trading stats."""
    summary = engine.get_account_summary()
    positions = engine.get_positions("open") + engine.get_positions("partial_closed")
    closed_today = engine.get_positions("closed")
    orders = engine.get_orders(limit=50)
    equity_history = engine.get_equity_history(limit=100)

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    today_closed = [p for p in closed_today if p.closed_at and p.closed_at.startswith(today)]

    # Stats
    total_trades = len(today_closed)
    wins = [p for p in today_closed if p.realized_pnl > 0]
    losses = [p for p in today_closed if p.realized_pnl <= 0]
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    avg_win = (sum(p.realized_pnl for p in wins) / len(wins)) if wins else 0
    avg_loss = (sum(p.realized_pnl for p in losses) / len(losses)) if losses else 0
    profit_factor = (abs(avg_win * len(wins)) / abs(avg_loss * len(losses))) if avg_loss != 0 and losses else None

    # Equity curve (mini sparkline)
    sparkline = _sparkline([e["equity"] for e in equity_history[-30:]])

    # Daily return
    daily_ret = (summary.daily_pnl / summary.initial_equity * 100) if summary.initial_equity > 0 else 0
    total_ret = ((summary.current_equity - summary.initial_equity) / summary.initial_equity * 100) if summary.initial_equity > 0 else 0

    # Build Feishu card
    elements: list[dict] = []

    # Header
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**📊 每日交易报告** {today}\n"
                f"━━━━━━━━━━━━━━━━━━"
            ),
        },
    })

    # Account overview
    pnl_emoji = "🟢" if summary.daily_pnl >= 0 else "🔴"
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**💰 账户概览**\n"
                f"初始权益: {summary.initial_equity:.2f} U\n"
                f"当前权益: {summary.current_equity:.2f} U ({total_ret:+.2f}%)\n"
                f"{pnl_emoji} 今日盈亏: {summary.daily_pnl:+.2f} U ({daily_ret:+.2f}%)\n"
                f"可用余额: {summary.available_balance:.2f} U\n"
                f"持仓数量: {summary.open_positions}/{5}"
            ),
        },
    })
    elements.append({"tag": "hr"})

    # Performance metrics
    pf_str = f"{profit_factor:.2f}" if profit_factor else "N/A"
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**📈 绩效指标**\n"
                f"今日交易: {total_trades} 笔\n"
                f"胜率: {win_rate:.1f}%\n"
                f"盈亏比: {pf_str}\n"
                f"累计已实现: {summary.total_realized_pnl:+.2f} U"
            ),
        },
    })
    elements.append({"tag": "hr"})

    # Open positions
    if positions:
        pos_lines = []
        for p in positions[:5]:
            side_emoji = "🟢" if p.side == "LONG" else "🔴"
            unrealized = 0  # Would need current price for real unrealized
            pos_lines.append(
                f"{side_emoji} **{p.symbol}** {p.side}\n"
                f"  入场: {p.entry_price:.2f} | 止损: {p.stop_loss:.2f}\n"
                f"  保证金: {p.margin_used:.2f} U | 状态: {p.status}"
            )
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**📦 当前持仓**\n" + "\n".join(pos_lines)},
        })
        elements.append({"tag": "hr"})

    # Today's closed trades
    if today_closed:
        trade_lines = []
        for t in today_closed[:10]:
            pnl_emoji = "✅" if t.realized_pnl > 0 else "❌"
            trade_lines.append(
                f"{pnl_emoji} {t.symbol} {t.side} | PnL: {t.realized_pnl:+.2f} U | {t.close_reason}"
            )
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**📋 今日成交**\n" + "\n".join(trade_lines)},
        })
        elements.append({"tag": "hr"})

    # Equity sparkline
    if sparkline:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**权益曲线**\n`{sparkline}`"},
        })

    # Footer
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "缠论量化纸交易系统 | 数据仅供参考，不构成投资建议"}],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"交易日报 {today}"},
            "template": "blue" if summary.daily_pnl >= 0 else "red",
        },
        "elements": elements,
    }


async def send_daily_report(
    engine: PaperEngine,
    app_id: str,
    app_secret: str,
    chat_id: str,
) -> str | None:
    """Build and send daily report to Feishu. Returns message_id or None."""
    if not app_id or not app_secret or not chat_id:
        log.warning("Feishu credentials not configured, skipping report")
        return None

    try:
        card = build_daily_report(engine)
        token = await get_tenant_token(app_id, app_secret)
        msg_id = await send_card(token, chat_id, card)
        log.info("Daily report sent to Feishu: %s", msg_id)
        return msg_id
    except Exception as e:
        log.error("Failed to send daily report: %s", e, exc_info=True)
        return None


def _sparkline(values: list[float], width: int = 20) -> str:
    """Generate a Unicode mini sparkline from numeric values."""
    if len(values) < 2:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn
    if rng < 1e-12:
        return chars[4] * min(len(values), width)
    step = max(1, len(values) // width)
    sampled = values[::step][-width:]
    return "".join(chars[min(len(chars) - 1, int((v - mn) / rng * (len(chars) - 1)))] for v in sampled)
