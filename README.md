# Chanlan — 缠论结构分析终端

基于缠论（缠中说禅理论）的数字货币技术分析平台。后端 FastAPI + 前端 React 19，覆盖从 K 线处理到买卖点判定的完整链路。

> **风险提示**：本工具仅供缠论结构与 AI 摘要的技术展示，不构成投资建议。任何买卖点与模型结论均非下单指令。交易风险由您自行承担。

## 架构

```
chanlan/
├── app/                          # FastAPI 后端
│   ├── main.py                   # 入口 + 静态文件挂载
│   ├── api/routes.py             # 8 个 API 端点
│   ├── services/                 # 核心业务逻辑
│   │   ├── chan_engine.py        # 缠论引擎（包含处理、分型、笔、中枢、背驰）
│   │   ├── analysis_pipeline.py  # 分析流水线
│   │   ├── backtest_quick.py     # 简化回测
│   │   ├── ai_glm_verdict.py     # GLM AI 摘要
│   │   ├── risk_controls.py      # 风控计算
│   │   └── ...                   # 15+ 服务模块
│   ├── trading/paper_orders.py   # 模拟盘 SQLite
│   └── db/                       # 数据库层（SQLite / PostgreSQL）
├── frontend/                     # React 19 前端
│   ├── src/
│   │   ├── app.tsx               # 根组件
│   │   ├── components/
│   │   │   ├── toolbar/          # 品种/周期选择、图层开关
│   │   │   ├── chart/            # ECharts K 线图 + 20+ 系列
│   │   │   ├── sidebar/          # 12 个功能卡片
│   │   │   └── layout/           # 主布局、进度条、页脚
│   │   ├── stores/               # Zustand 状态管理
│   │   ├── lib/                  # API 层、格式化工具
│   │   ├── constants/            # 调色板、图层预设、标签映射
│   │   └── types/                # TypeScript 类型定义
│   └── vite.config.js            # Vite 8 + React + Tailwind v4
├── static_dist/                  # 前端构建产物（后端直接托管）
├── tests/                        # pytest 测试
├── start.sh / stop.sh            # 一键启停脚本
└── docs/                         # 产品规划文档
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.9+, FastAPI, Pydantic v2, SQLAlchemy (async) |
| 前端 | React 19, TypeScript, Vite 8, HeroUI v3, Tailwind CSS v4 |
| 图表 | ECharts 5.5 (npm) |
| 状态 | Zustand (persist 中间件 → localStorage) |
| 数据库 | SQLite（默认）/ PostgreSQL（可选） |
| AI | 智谱 GLM（可选，浏览器本地保存 API Key） |

## 快速启动

```bash
# 一键启动（自动安装依赖）
./start.sh

# 或手动启动
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload          # 后端 :8000
cd frontend && npm install && npm run dev  # 前端 :5173
```

打开 `http://localhost:5173`。

停止服务：`./stop.sh`

## 核心功能

### 缠论分析引擎
- **K 线包含处理** — 按走势方向合并包含 K 线
- **分型识别** — 三根 K 线构成的顶/底分型
- **笔划分** — 顶底交替，最小间隔 5 根合并 K 线
- **线段划分** — 67 课特征序列法（strict67）或 legacy 三笔重叠
- **中枢检测** — 三笔重叠区间 [ZD, ZG]，支持本级 / 线段级 / 上级
- **背驰判定** — MACD 柱面积比较 + 几何比率
- **买卖点** — 一二三类买卖点，含止损/止盈/R:R 比值

### 前端交互
- **ECharts K 线图** — 20+ 可切换系列（笔、线段、中枢带、买卖点标注、背驰点、BOLL、RSI）
- **图层开关** — 13 个独立开关 + 3 个预设（看盘/复盘/极简）
- **多周期分析** — 并行请求 5 个周期，一键切换到主图
- **风控试算** — 输入净值/风险比例/止损价差 → 仓位/保证金/强平价
- **演示回测** — 信号撮合 + 手续费，输出总收益/最大回撤/Sharpe
- **纸盘记账** — 服务端 SQLite 模拟交易记录
- **交易纪律** — 连续亏损熔断计数 + 交易假设记录

### AI 摘要（可选）
- 浏览器本地保存智谱 GLM API Key
- 分析后自动请求 AI 摘要，显示在结论面板

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/analyze` | 缠论分析（品种 + 周期） |
| POST | `/analyze/multi` | 多周期并行分析 |
| POST | `/analyze/verdict` | GLM AI 摘要 |
| POST | `/risk/position-size` | 风控试算 |
| POST | `/trade/paper` | 模拟下单 |
| GET | `/trade/paper/recent` | 最近模拟记录 |
| POST | `/backtest/quick` | 简化回测 |
| GET | `/symbols` | 可用品种列表 |

```bash
# 示例
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"market":"crypto","symbol":"BTCUSDT","interval":"240","limit":2500}'
```

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CHANLAN_PORT` | `8000` | 后端端口 |
| `CHANLAN_STATIC_DIR` | `static` | 静态文件目录（设为 `static_dist` 托管构建产物） |
| `CHANLAN_PAPER_ORDERS_DB_PATH` | `.cache/chanlan/paper_orders.sqlite` | 模拟盘数据库路径 |
| `CHANLAN_ANALYZE_DISK_CACHE_ENABLED` | `true` | 分析缓存开关 |
| `CHANLAN_DATABASE_URL` | — | PostgreSQL 连接串（可选，启用 K 线缓存） |
| `CHANLAN_SYNC_ENABLED` | `false` | Binance WebSocket 实时 K 线同步（需 PG） |

## 缠论规则说明

这是工程化 MVP，规则集中在 `app/services/chan_engine.py`：

1. **包含处理** — 按当前走势方向合并包含 K 线
2. **分型** — 三根 K 线顶/底分型
3. **笔** — 顶底交替，最小间隔 5 根合并后 K 线
4. **中枢** — 连续三笔价格区间重叠后形成，向后延伸
5. **背驰** — 同方向当前笔价格创新高/新低，MACD 柱面积低于上一同向笔的 80%
6. **TD** — TD Setup 9（暂未实现 Countdown 13）

## License

Private project. All rights reserved.
