"""纸上 SQLite：写入 / 列表 / 超限时裁剪旧记录。"""

from __future__ import annotations

from app.core.config import settings
from app.trading import paper_orders as po


def test_record_and_recent_roundtrip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "paper_orders_db_path", str(tmp_path / "paper.sqlite"))
    monkeypatch.setattr(settings, "paper_orders_max_rows", 100)
    oid = po.record_paper_order(symbol="BTCUSDT", side="BUY", quantity=1.0, note="t")
    assert oid
    rows = po.recent_orders(10)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"
    assert rows[0]["side"] == "BUY"
    assert rows[0]["order_id"] == oid


def test_prune_keeps_newest(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "paper_orders_db_path", str(tmp_path / "paper.sqlite"))
    monkeypatch.setattr(settings, "paper_orders_max_rows", 3)
    for i in range(5):
        po.record_paper_order(symbol="X", side="BUY", quantity=1.0, note=str(i))
    rows = po.recent_orders(10)
    assert len(rows) == 3
    notes = {r["note"] for r in rows}
    assert notes == {"2", "3", "4"}
