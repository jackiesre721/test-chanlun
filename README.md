# Chanlan — 缠论结构分析终端

基于缠论（缠中说禅理论）的数字货币技术分析平台。后端 FastAPI + 前端 React 19，覆盖从 K 线处理到买卖点判定的完整链路。

> **风险提示**：本工具仅供缠论结构与 AI 摘要的技术展示，不构成投资建议。任何买卖点与模型结论均非下单指令。交易风险由您自行承担。

## 架构

```
chanlan/
├── app/                          # FastAPI 后端
│   ├── main.py                   # 入口 + 静态文件挂载 + lifespan
│   ├── api/
│   │   ├── routes.py             # 13 个 API 端点
│   │   └── dependencies.py       # 依赖注入
│   ├── core/
│   │   ├── config.py             # 40+ 可配置项（环境变量前缀 CHANLAN_）
│   │   ├── models.py             # Pydantic 数据模型（50+ 个模型类）
│   │   └── errors.py             # 自定义异常 + 全局错误处理
│   ├── services/                 # 核心业务逻辑
│   │   ├── chan_engine.py        # 缠论引擎（2200+ 行，包含处理→分型→笔→线段→中枢→背驰→买卖点）
│   │   ├── analysis_pipeline.py  # 分析流水线编排（23 步完整链路）
│   │   ├── analyzer.py           # 业务服务层 + 多周期映射
│   │   ├── backtest_quick.py     # 信号驱动回测（共振过滤 + 策略过滤 + 模拟撮合）
│   │   ├── ai_glm_verdict.py     # 智谱 GLM AI 判定（支持 Anthropic 兼容模式）
│   │   ├── ai_structure_hint.py  # 结构语境评分（启发式）
│   │   ├── action_focus.py       # 当下关注点分析
│   │   ├── chan_advanced.py      # 高级结构（区间套 + a+A+b+B+c + 趋势递归）
│   │   ├── risk_controls.py      # 风控计算（仓位 + ATR 追踪止损）
│   │   ├── indicators.py         # MACD / BOLL / RSI / TD9
│   │   ├── divergence_metrics.py # 多维度背驰力度对比（7 种度量）
│   │   ├── macd_geometry.py      # MACD 几何特征（驼峰能量/极值收缩）
│   │   ├── stroke_metrics.py     # 笔力度指标（斜率/角度/R²/SNR）
│   │   ├── pivot_symmetry.py     # 中枢对称性
│   │   ├── lines_form.py         # 走势形态标签
│   │   ├── trend_type_segment.py # 线段走势类型判定
│   │   ├── kline_hierarchy.py    # K 线父子层级映射
│   │   ├── fake_bi.py            # 笔内虚拟笔
│   │   ├── bar_generator.py      # K 线合成（低周期→高周期）
│   │   ├── incremental_chan.py   # 增量分析（流式 K 线推送）
│   │   ├── analysis_cache.py     # MACD 序列缓存
│   │   ├── analyze_disk_cache.py # 分析结果磁盘缓存
│   │   └── symbol_registry.py    # 品种白名单（5 个 USD-M 合约）
│   ├── repositories/
│   │   └── market_data.py        # Binance USD-M 合约数据仓库（自动分页）
│   ├── trading/
│   │   └── paper_orders.py       # 模拟盘 SQLite
│   └── db/
│       ├── engine.py             # SQLAlchemy async 引擎
│       ├── kline_store.py        # PostgreSQL K 线缓存
│       ├── sync.py               # 历史数据回填
│       └── ws_listener.py        # Binance WebSocket 实时 K 线
├── frontend/                     # React 19 前端
│   ├── src/
│   │   ├── app.tsx               # 根组件（监听 symbol/interval 自动分析）
│   │   ├── components/
│   │   │   ├── toolbar/          # 品种/周期选择、图层预设（3 种）、图层开关（11 个）
│   │   │   ├── chart/            # ECharts K 线图（18 个数据系列 + 回测叠加）
│   │   │   ├── sidebar/          # 4 Tab、13 个功能卡片
│   │   │   └── layout/           # 主布局、加载遮罩、页脚
│   │   ├── stores/               # Zustand 状态管理（6 个 store，支持 localStorage 持久化）
│   │   ├── lib/                  # API 客户端、ECharts 辅助、格式化工具
│   │   ├── constants/            # 调色板（34 色）、图层预设、标签映射、周期映射
│   │   └── types/                # TypeScript 类型定义
│   └── vite.config.js            # Vite 8 + React + Tailwind v4
├── static_dist/                  # 前端构建产物（后端直接托管）
├── tests/                        # pytest 测试（18 个测试文件）
├── start.sh / stop.sh            # 一键启停脚本
├── docs/                         # 架构文档与规划
│   ├── PROJECT_ARCHITECTURE.md   # 完整技术详解（800 行）
│   └── ...                       # 回测基准、优化记录、路线图
└── pyproject.toml                # Python 项目配置
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.9+, FastAPI, Pydantic v2, SQLAlchemy (async), uvicorn |
| 前端 | React 19, TypeScript 6, Vite 8, HeroUI v3, Tailwind CSS v4 |
| 图表 | ECharts 5.6 (echarts-for-react) |
| 状态 | Zustand 5 (persist 中间件 → localStorage) |
| 数据源 | Binance USD-M 永续合约 API |
| 数据库 | SQLite（模拟盘）/ PostgreSQL（可选，K 线缓存 + WebSocket 实时同步） |
| AI | 智谱 GLM（可选，Anthropic 兼容模式，浏览器本地保存 API Key） |

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

### 缠论分析引擎（23 步流水线）

```
原始 K 线 → 包含处理 → 分型识别 → 笔构建（含浅反向折叠）
→ 笔力度指标 → 未完成笔 → 线段构建（legacy / strict67）
→ 笔中枢 + 线段中枢 → 中枢对称性 → MACD / BOLL / RSI
→ 笔级背驰 + 段级背驰 → 走势形态 → 虚拟笔
→ 笔级买卖点 + 段级买卖点 → 信号过滤（盈亏比 + 趋势 + 段级标记）
→ 段级止损映射 → 当下关注点 → TD9 → 高级结构（区间套 + 趋势递归）
```

- **K 线包含处理** — 按走势方向合并包含 K 线，`merged_from` 支持溯源
- **分型识别** — 三根 K 线严格双极值顶/底分型，含进行中分型与强度评分
- **笔划分** — 顶底交替，最小间隔 5 根；可选浅反向笔折叠（22% 阈值）
- **线段划分** — `legacy`（三笔重叠延伸）或 `strict67`（67 课特征序列法，情形一 + 情形二）
- **中枢检测** — 笔中枢 + 线段中枢，支持相邻重叠合并、对称性评分
- **背驰判定** — 7 种 MACD 度量（area/hump/peak/slope/either/either_loose/both）+ 可选闸门（零轴/极值收缩/DIF 穿轴）
- **买卖点** — 一二三类 + 类二 + 类三 + 二类延伸 + TD9，共 7 种信号，含止损/止盈1/止盈2/R:R
- **多周期** — 自动映射高级别笔/中枢到低周期，趋势递归共振判定
- **高级结构** — a+A+b+B+c 分解、Zn 价格、笔停顿、缺口统计、线段走势段

### 回测引擎

- **信号驱动成交** — 逐 K 线模拟，支持止损检查 + 杠杆强平
- **共振过滤** — 多级别趋势对齐，跨级背离时仅保留一类信号
- **策略过滤** — 跳过一类/类三，中枢内信号回避（保留类二）
- **仓位管理** — 二/三类全仓，二类延伸/类二半仓
- **统计** — 胜率、盈亏比、Sharpe、最大回撤、按信号类型分类统计
- **交易叠加** — 回测买卖点可叠加到 K 线图上

### 前端交互

- **ECharts K 线图** — 18 个可切换系列（笔、线段、中枢带、买卖点标注、背驰点、BOLL、MACD、RSI、回测叠加）
- **图层控制** — 11 个独立开关 + 3 个预设（看盘 / 复盘 / 极简）
- **侧栏 4 Tab、13 卡片**：
  - **当下**：多空判定、当下关注点、信号详情、结构统计
  - **执行与风控**：仓位计算器、模拟交易、交易纪律（连续亏损熔断）
  - **研究与回测**：多周期并行分析、快速回测（含权益曲线 + 交易明细表）、信号表现统计
  - **参考与设置**：高级结构分析（区间套/趋势递归）、缠论规则说明、GLM API 配置
- **风控试算** — 输入净值/风险比例/止损价差 → 仓位/保证金/强平价；ATR 追踪止损
- **纸盘记账** — 服务端 SQLite 模拟交易记录
- **过滤信号开关** — 可选显示被盈亏比/趋势过滤的信号（半透明标记）

### AI 摘要（可选）

- 支持 Anthropic 兼容模式（默认）或 OpenAI 兼容模式连接智谱 GLM
- 分析后自动请求 AI 摘要，输出多空方向、置信度、参考价位
- API Key 浏览器本地保存，不经过服务端

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/symbols` | 可用品种列表（5 个 USD-M 合约） |
| POST | `/tools/aggregate-bars` | K 线合成为目标周期 |
| POST | `/analyze` | 缠论分析（品种 + 周期） |
| POST | `/analyze/multi` | 多周期并行分析 |
| POST | `/backtest/quick` | 快速回测 |
| POST | `/risk/position-size` | 仓位计算 |
| POST | `/risk/trailing-stop` | ATR 追踪止损 |
| POST | `/trade/paper` | 模拟下单 |
| GET | `/trade/paper/recent` | 最近模拟记录 |
| POST | `/ai/structure-hint` | 结构评分（启发式） |
| POST | `/analyze/verdict` | GLM AI 判定（同时挂载 `/ai/verdict`、`/api/ai/verdict`） |

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
| `CHANLAN_STATIC_DIR` | `static_dist` | 静态文件目录 |
| `CHANLAN_PAPER_ORDERS_DB_PATH` | `.cache/chanlan/paper_orders.sqlite` | 模拟盘数据库路径 |
| `CHANLAN_ANALYZE_DISK_CACHE_ENABLED` | `true` | 分析结果磁盘缓存 |
| `CHANLAN_DATABASE_URL` | — | PostgreSQL 连接串（可选，启用 K 线缓存） |
| `CHANLAN_SYNC_ENABLED` | `false` | Binance WebSocket 实时 K 线同步（需 PG） |
| `CHANLAN_SEGMENT_ENGINE` | `legacy` | 线段算法：`legacy` 或 `strict67` |
| `CHANLAN_DIVERGENCE_MACD_METRIC` | `area` | 背驰力度度量（7 种可选） |
| `CHANLAN_DIVERGENCE_RATIO` | `0.8` | 背驰判定阈值 |
| `CHANLAN_STROKE_COLLAPSE_SHALLOW_REVERSAL` | `true` | 是否折叠浅反向笔 |
| `CHANLAN_FRACTAL_INCLUDE_TENTATIVE` | `true` | 是否检测进行中分型 |
| `CHANLAN_ANALYZE_MAX_BARS` | `5000` | 单次分析最大 K 线数 |
| `CHANLAN_BACKTEST_MAX_BARS` | `30000` | 回测最大 K 线数 |
| `CHANLAN_ZHIPU_API_MODE` | `anthropic` | GLM 接口模式（`anthropic` / `openai_compat`） |

完整配置项见 `app/core/config.py`（40+ 个环境变量）。

## 支持品种

Binance USD-M 永续合约：**BTCUSDT**、**ETHUSDT**、**SOLUSDT**、**XAUUSDT**、**DOGEUSDT**

## 支持周期

1m、5m、15m、30m、1h、4h、1d、1w、1M（共 9 个）

## 测试

```bash
pytest                              # 运行全部测试
pytest tests/test_chan_engine.py    # 单个模块
```

## License

Private project. All rights reserved.
