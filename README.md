# Chanlan 缠论分析 MVP

一个无认证的 Python 版缠论分析小系统，参考海哥缠论页面的核心交互：

- 数字货币品种选择，默认 `BTCUSDT` / `4小时`
- Binance spot K 线数据
- 本级笔、中级别笔、中枢、中级别中枢
- MACD 背驰买卖点
- TD9 摘要
- ECharts K 线渲染

## 启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

打开 `http://127.0.0.1:8000`。

## 本地持久化（默认）

- **模拟盘** `POST /trade/paper`：SQLite（默认 `.cache/chanlan/paper_orders.sqlite`，可用 `CHANLAN_PAPER_ORDERS_DB_PATH`）。
- **分析缓存**：命中相同锚点时跳过远程拉取与重算（默认 `.cache/analyze/`，可用 `CHANLAN_ANALYZE_DISK_CACHE_ENABLED=false` 关闭）。

## API

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"market":"crypto","symbol":"BTCUSDT","interval":"240","limit":2500}'
```

## 当前规则说明

这是工程化 MVP，不是最终交易策略：

- 包含处理：按当前走势方向合并包含 K 线。
- 分型：三根 K 线顶/底分型。
- 笔：顶底交替，最小间隔 5 根合并后 K 线。
- 中枢：连续三笔价格区间重叠后形成，并向后延伸。
- 背驰：同方向当前笔价格创新高/新低，但 MACD 柱面积低于上一同向笔的 80%。
- TD：实现 TD Setup 9，暂未实现 Countdown 13。

后续如果要更贴近某一派缠论规则，优先调整 `app/services/chan_engine.py` 的纯函数。
