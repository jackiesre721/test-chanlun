# 缠论结构终端 — 项目架构与技术详解

> 生成日期：2026-05-06
> 代码版本：`strict-chan-v18` · `segment_engine=legacy`

---

## 1. 项目概述

本项目是一个**缠论（缠中说禅理论）**的完整量化分析平台，用于加密货币（BTC/ETH/SOL/XAU/DOGE）的 K 线结构分析、买卖点识别与策略回测。系统采用前后端分离架构：

- **后端**：Python (FastAPI)，核心缠论引擎 2223 行，实现了从 K 线标准化到买卖点生成的完整几何流水线
- **前端**：React 19 + TypeScript + ECharts，交互式 K 线图展示笔/线段/中枢/买卖点/背驰等缠论结构
- **数据源**：Binance USD-M 永续合约 API，支持 1 分钟到 1 月共 9 个周期

---

## 2. 技术架构

### 2.1 后端架构

```
app/
├── api/
│   ├── routes.py              # FastAPI 路由（13 个端点）
│   └── dependencies.py        # 依赖注入
├── core/
│   ├── config.py              # 43 个可配置项（环境变量前缀 CHANLAN_）
│   └── models.py              # Pydantic 数据模型（30+ 个模型类）
├── services/
│   ├── chan_engine.py          # 缠论几何引擎核心（2223 行）
│   ├── analysis_pipeline.py   # 分析流水线编排（284 行）
│   ├── analyzer.py             # 业务服务层 + 多周期映射（233 行）
│   ├── backtest_quick.py       # 快速回测引擎（461 行）
│   ├── action_focus.py         # 当下关注点分析（161 行）
│   ├── indicators.py           # MACD / BOLL / RSI / TD9 指标
│   ├── divergence_metrics.py   # 多维度背驰力度对比
│   ├── macd_geometry.py        # MACD 几何特征（驼峰能量/极值收缩等）
│   ├── ai_glm_verdict.py       # 智谱 GLM AI 判定
│   └── symbol_registry.py      # 币种白名单（5 个交易对）
├── repositories/
│   └── market_data.py          # Binance 数据仓库（支持 PG 缓存）
└── db/
    └── kline_store.py          # PostgreSQL K 线缓存（可选）
```

### 2.2 前端架构

```
frontend/src/
├── app.tsx                     # 根组件，监听 symbol/interval 变化自动分析
├── main.tsx                    # 入口
├── components/
│   ├── chart/
│   │   ├── echarts-chart.tsx   # 核心 K 线图（raw echarts.init）
│   │   ├── chart-options/      # 图表配置构建器（15 个数据系列）
│   │   └── chart-pane.tsx      # 图表面板
│   ├── toolbar/                # 工具栏（币种/周期/图层预设/开关）
│   └── sidebar/                # 侧栏（4 个 Tab，12 个功能卡片）
├── stores/
│   ├── settings-store.ts       # 设置（持久化到 localStorage）
│   ├── analysis-store.ts       # 分析结果（会话级）
│   ├── risk-store.ts           # 风控参数（持久化）
│   ├── discipline-store.ts     # 交易纪律（持久化）
│   ├── glm-store.ts            # GLM 配置与判定（持久化）
│   └── backtest-overlay-store.ts # 回测叠加层（会话级）
├── lib/
│   ├── api.ts                  # API 客户端（8 个端点）
│   ├── echarts-helpers.ts      # 图表辅助（缩放/导航/价格轴）
│   └── format.ts               # 格式化工具
├── types/
│   └── analysis.ts             # TypeScript 类型定义
└── constants/
    ├── chart-palette.ts        # 34 个颜色常量
    ├── level-maps.ts           # 周期映射 + 信号标签
    ├── label-maps.ts           # 趋势/共振标签
    └── layer-presets.ts        # 11 个图层开关 + 3 个预设
```

**技术栈**：React 19 · TypeScript 6 · Vite 8 · HeroUI v3 · Zustand 5 · ECharts 5.6 · Tailwind CSS 4

### 2.3 API 端点一览

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/symbols` | 获取支持的交易对 |
| POST | `/analyze` | 单周期缠论分析（核心） |
| POST | `/analyze/multi` | 多周期并行分析 |
| POST | `/backtest/quick` | 快速回测 |
| POST | `/risk/position-size` | 仓位计算器 |
| POST | `/risk/trailing-stop` | ATR 追踪止损 |
| POST | `/trade/paper` | 模拟下单 |
| GET | `/trade/paper/recent` | 最近模拟记录 |
| POST | `/ai/structure-hint` | 结构评分 |
| POST | `/analyze/verdict` | GLM AI 判定 |

---

## 3. 缠论几何引擎

引擎位于 `chan_engine.py`，按以下顺序执行流水线：

```
原始 K 线 → 标准化（包含处理） → 分型识别 → 笔构建 → 线段构建
→ 笔中枢 / 线段中枢 → 背驰检测 → 买卖点生成
```

### 3.1 K 线标准化（包含处理）

**函数**：`normalize_candles(candles)`

当相邻两根 K 线存在**包含关系**（一根的高低完全覆盖另一根）时合并为一根：

- **下降趋势**中：取较低的高 + 较低的低（保留空头方向）
- **上升趋势**中：取较高的高 + 较高的低（保留多头方向）

合并后的 K 线通过 `merged_from` 字段记录参与合并的原始 K 线索引，支持溯源。

### 3.2 分型识别

**函数**：`find_fractals(candles)`

在标准化后的 K 线上识别三根 K 线的组合：

- **顶分型**：中间 K 线的高 > 两侧的高 **且** 中间 K 线的低 > 两侧的低（严格双极值）
- **底分型**：中间 K 线的低 < 两侧的低 **且** 中间 K 线的高 < 两侧的高

每个分型附带 `strength_hint`（0~1），基于实体占比、中间 K 线幅度、收盘位置等因素综合评分。

最后一根 K 线可标记为 `confirmed=False` 的**进行中分型**（通过 `include_tentative` 配置控制）。

### 3.3 笔的构建

**函数**：`build_strokes(fractals, min_gap=4)`

从确认的分型序列中构建笔：

1. **同类型连续分型**：保留更极端的那个（更高的顶或更低的底）
2. **不同类型分型**：检查最小间距（至少 4 根标准化 K 线），验证价格方向合理性
3. **浅反向笔折叠**（`stroke_collapse_shallow_reversal`）：三笔序列中如果中间反转笔幅度过小（< 22%），自动合并

每根笔还通过 `hydrate_stroke_metrics` 填充：
- `length_bars`：经历 K 线数
- `price_change`：价格变动
- `slope_per_bar` / `angle_deg`：斜率和角度
- `power_price` / `power_volume`：价格/成交量力度
- `rsq_close`：R² 拟合度
- `power_snr`：信噪比

### 3.4 线段的构建

**函数**：`build_segments(strokes)`

支持两种线段引擎（通过 `CHANLAN_SEGMENT_ENGINE` 配置）：

#### 3.4.1 Legacy 模式（默认）

扫描连续三笔的价格区间是否有重叠。只要三笔重叠即形成线段，延伸直到后续笔不再重叠或不再延续方向。

#### 3.4.2 Strict67 模式（第 67 课标准）

实现完整的**特征序列**方法：

1. 按线段方向提取特征序列元素（每笔的高低范围视为一根"虚拟 K 线"）
2. 对特征序列做**非包含合并**（与 K 线包含处理逻辑相同）
3. 在合并后的特征序列上寻找**顶/底分型**
4. **情形一**：分型的前两个元素有价格重叠 → 直接作为线段终点
5. **情形二**：分型前两个元素有缺口 → 需要在后续子序列中找到**第二特征序列分型**才确认终点
6. 未命中时回退到 Legacy 延伸算法

### 3.5 中枢的构建

#### 3.5.1 笔中枢

**函数**：`build_pivots(strokes)`

连续三笔的价格区间有重叠即形成笔中枢：

```
ZG = min(三笔各自最高价)
ZD = max(三笔各自最低价)
要求 ZD < ZG
```

中枢形成后，步进 3 笔（避免滑动窗口重复），后续还进行去重和可选的相邻重叠中枢合并。

#### 3.5.2 线段中枢

**函数**：`build_segment_pivots(segments)`

连续三个线段的价格区间有重叠即形成线段中枢。初始三段核心形成后，可延伸包含后续仍与 [ZD, ZG] 相交的线段，重新收紧 ZD/ZG。

#### 3.5.3 中枢属性

每个中枢记录：

| 字段 | 含义 |
|------|------|
| `start_bi` / `end_bi` | 起止笔/线段索引 |
| `start_idx` / `end_idx` | 起止 K 线索引 |
| `zg` / `zd` | 中枢上界/下界 |
| `level` | `"bi"`（笔中枢）或 `"segment"`（线段中枢） |
| `entry_seg_idx` | 进入段索引 |
| `leave_seg_idx` | 离开段索引 |
| `direction` | 离开段方向 |
| `symmetry_balance` | 收盘价在 [ZD,ZG] 上下侧的平衡度（0~1） |

### 3.6 背驰检测

**函数**：`build_divergences(movements, pivots, macd_points)`

对每个中枢，比较**进入段**与**离开段**的力度：

1. 提取 MACD 四个维度指标：
   - `macd_area`：柱状图总面积
   - `hump_energy`：驼峰能量（同号柱的累计能量）
   - `hist_peak_max`：柱状图最大峰值
   - `price_slope_per_bar`：每根标准化 K 线的价格变动

2. 根据 `divergence_macd_metric` 配置选择对比方式：
   - `area`：面积比
   - `hump`：驼峰能量比
   - `peak`：峰值比
   - `slope`：斜率比
   - `either` / `either_loose`：多维度任一减弱即可
   - `both`：所有维度都减弱

3. 离开段力度弱于进入段 → 背驰成立

4. **结构分类**：
   - **趋势背驰**：相邻中枢的价格区间不重叠且堆叠（离开段还必须创出更高/更低价）
   - **盘整类背驰**：中枢区间重叠或不满足趋势背驰条件

5. **可选闸门**：
   - `divergence_require_pivot_macd_zero_axis`：中枢内 DIF 必须接近零轴
   - `divergence_require_macd_extrema_shrink`：MACD 极值必须收缩
   - `divergence_require_leave_segment_zero_cross`：离开段 DIF 必须穿越零轴

---

## 4. 买卖点信号体系

系统识别 **7 种信号类型**，分两个级别（笔级 `"bi"` 和线段级 `"segment"`）：

| Kind | 中文名 | 前置条件 | 强度 |
|------|--------|----------|------|
| `first` | 一买/一卖 | 中枢 + 背驰 | 动态计算 |
| `second` | 二买/二卖 | 一类信号后的回踩确认 | 0.70 |
| `second_extend` | 二买/二卖延伸 | 二类信号后的再次确认 | 0.64 |
| `third` | 三买/三卖 | 离开中枢后的回踩确认 | 0.80 |
| `second_class` | 类二买/类二卖 | 中枢内抬底/压顶 | 0.62/0.58/0.55 |
| `third_class` | 类三买/类三卖 | 浅离开中枢后的回踩（< 10% 中枢高度） | 0.66 |
| `td9` | TD9 | TD Sequential 计数达 9 | 1.00 |

### 4.1 一类买卖点（first）

**触发条件**：某中枢处检测到背驰（离开段 MACD 力度弱于进入段）。

**一买（first BUY）**：
- 背驰方向为 DOWN（价格向下离开中枢但力度减弱）
- 入场价 = 离开段末端价格
- 止损 = `ZD - 0.15 × (ZG - ZD)`（中枢下界再下浮 15% 高度）
- 止盈1 = `price + 1 × (price - stop_loss)`（1:1 盈亏比）
- 止盈2 = `price + 2 × (price - stop_loss)`（2:1 盈亏比）
- 强度 = `clamp(1 - leave_area / entry_area, 0, 1)`

**一卖（first SELL）**：镜像对称。

**盘整一类（T1P）**：当尚无中枢形成时，检测最近三笔的"同向-反向-同向"模式，如果后一个同向笔未创新低/新高且 MACD 减弱，产生一类信号。

### 4.2 二类买卖点（second）

**触发条件**：一类信号之后，紧接着的三个运动段形成"回踩 + 确认"模式。

**二买**：
- 回踩段方向 = UP（一类买入后的反弹）
- 确认段方向 = DOWN（再次回调）
- 确认段末端价格 > 一类信号价格（底部抬高）
- 入场价 = 确认段末端价格
- 止损 = 一类信号价格
- 止盈2 = `price + 2 × (price - first_price)`

**二卖**：镜像对称（确认段末端价格 < 一类信号价格，顶部压低）。

### 4.3 二类延伸（second_extend / T2S）

**触发条件**：二类信号之后，在同一中枢上下文中再次出现"回踩 + 确认"。

**二买延伸**：
- 确认段末端价格 > 二类信号价格 且 > 一类信号价格（底部持续抬高）
- 入场价 = 确认段末端价格
- 止损 = 二类信号价格（以二类为支撑）
- 强度 = 0.64

由 `enable_t2s_second_extend` 配置控制是否启用。

### 4.4 三类买卖点（third）

**触发条件**：一类信号之后，运动段**离开中枢**后回踩确认。

**三买**：
- 离开段 = UP（向上离开中枢，exit > ZG）
- 回踩段 = DOWN
- 回踩最低价 > ZG（未回落至中枢内）
- 确认段 = UP
- 入场价 = 确认段末端价格
- 止损 = `ZG - 0.15 × (ZG - ZD)`（以中枢上界为支撑）
- 强度 = 0.80

**三卖**：镜像（离开段 = DOWN，回踩 < ZD，止损 = `ZD + 0.15 × height`）。

### 4.5 独立三类/类三买卖点

**不依赖**于一类背驰，独立扫描每个中枢：

**独立三买**：从中枢结束后扫描 leave + retrace + confirm 模式：
- 离开段 = UP（exit > ZG）
- 回踩段 = DOWN（最低价 > ZG）
- 确认段 = UP
- 如果离开深度很浅（离开距离 < 10% 中枢高度）→ 标记为 `third_class`（类三），否则为 `third`
- 类三强度 = 0.66，正常三类强度 = 0.78

### 4.6 类二买卖点（second_class）

中枢内震荡时检测抬底/压顶模式，有两个独立来源：

#### 来源一：中枢内类二（`_class_like_second_signals`）

仅限笔级中枢。在中枢内部扫描 DOWN-UP-DOWN（买）或 UP-DOWN-UP（卖）模式：

**类二买**：
- 第一个 DOWN 的低点（lo_a）在中枢内或中枢下方不超过 `2 × pivot_height` 或 `2%`
- 第二个 DOWN 的低点（lo_c）> lo_a（底部抬高）
- 入场价 = c.end_price
- 止损 = `lo_a - 0.15 × pivot_height`
- 强度：中枢内 = 0.62，中枢外 = 0.58

#### 来源二：独立形态二类（`_standalone_second_signals_for_pivot`）

在中枢之后最多 12 笔中扫描 DOWN-UP-DOWN / UP-DOWN-UP 模式：

- 类二买：后者低点比前者高至少 0.1%，且不在中枢内（由来源一处理）
- 强度 = 0.55

### 4.7 TD9 信号

独立的纯价格序列指标，不依赖中枢：

- 从第 5 根 K 线起，比较当前收盘价与 4 根前的收盘价
- 连续 9 次收高 → `SELL` 信号（上涨耗尽）
- 连续 9 次收低 → `BUY` 信号（下跌耗尽）
- 强度 = 1.00，无止损/止盈

### 4.8 信号去重与过滤

1. **去重**：同一 `(pivot_level, pivot_idx, side, kind)` 只保留最新的信号
2. **段级信号标记**：段级一类信号标记 `rr_filtered = True`（仅保留二类/三类/类二/类三）
3. **盈亏比过滤**：有止损时要求 reward/risk >= 1.5
4. **趋势过滤**：明确上升趋势中过滤三类卖点，明确下降趋势中过滤三类买点
5. **段级止损映射**：为段级信号计算笔级止损（`stop_loss_2`），基于包含该信号位置的笔中枢
6. 最终输出最近 30 个买信号和 30 个卖信号

---

## 5. 止损止盈计算汇总

**统一缓冲比例**：`_STOP_LOSS_BUFFER_RATIO = 0.15`（15% 中枢高度）

| 信号类型 | 方向 | 止损公式 |
|----------|------|----------|
| 一类 | 买 | `ZD - 0.15 × (ZG - ZD)` |
| 一类 | 卖 | `ZG + 0.15 × (ZG - ZD)` |
| 二类 / 二类延伸 | 买 | 一类信号价格 |
| 二类 / 二类延伸 | 卖 | 一类信号价格 |
| 三类 / 类三 | 买 | `ZG - 0.15 × (ZG - ZD)` |
| 三类 / 类三 | 卖 | `ZD + 0.15 × (ZG - ZD)` |
| 类二 | 买 | `lo_a - 0.15 × pivot_height` |
| 类二 | 卖 | `hi_a + 0.15 × pivot_height` |

**止盈统一公式**：
- TP1（1:1）：`price ± (price - stop_loss)`
- TP2（2:1）：`price ± 2 × (price - stop_loss)`

---

## 6. 多级别分析（区间套）

### 6.1 周期映射

```
1m → 5m → 30m → 4h → 1d → 1w → 1M
      ↑
   15m → 1h → 4h → 1d → 1w → 1M
```

### 6.2 映射流程

**函数**：`project_higher_onto_base(base_candles, higher_candles)`

1. 分别对高周期 K 线做标准化 → 分型 → 笔 → 线段 → 笔中枢 + 线段中枢
2. 将高周期的笔和中枢**投影**到低周期的时间轴上
3. 映射算法：用高周期 K 线的 `open_time` 区间做 `bisect_left` 定位低周期 K 线范围，然后在范围内选择与目标价格最接近的 K 线作为映射点

### 6.3 趋势共振判定

**函数**：`build_chan_advanced_context` 中的趋势递归分析

综合高周期和低周期的走势形态，输出 `composite` 判定：

| composite | 含义 |
|-----------|------|
| `aligned_uptrend` | 多级别一致看多 |
| `aligned_downtrend` | 多级别一致看空 |
| `aligned_consolidation` | 多级别一致震荡 |
| `cross_level_divergent` | 级别间方向矛盾 |
| `partially_aligned` | 部分级别对齐 |
| `insufficient_higher_data` | 高周期数据不足 |

### 6.4 前端展示

- 本级别笔 → 白色实线（`rgba(255,255,255,0.78)`）
- 高级别笔（段） → 蓝色实线（`#42a5f5`），通过插值绘制为穿过所有组成笔的折线
- 本级别中枢 → 白色半透明矩形（`rgba(255,255,255,0.12)`）
- 高级别中枢 → 蓝色半透明矩形（`rgba(66,165,245,0.18)`），虚线边框

---

## 7. 分析流水线完整流程

**函数**：`build_analyze_bundle_from_normalized`（`analysis_pipeline.py`）

```
输入: 标准化 K 线 + 高周期笔/中枢（可选）

1. find_fractals()            → 分型列表
2. build_strokes()             → 笔列表
3. hydrate_stroke_pause()      → 笔的收盘突破标记
4. hydrate_stroke_metrics()    → 笔的力度指标
5. build_active_stroke()       → 未完成笔（进行中）
6. build_segments()            → 线段列表
7. build_pivots(strokes)       → 笔中枢
8. build_segment_pivots()      → 线段中枢
9. hydrate_pivot_symmetry()    → 中枢对称性
10. display_macd_for_analysis() → MACD 数据
11. bollinger_bands()           → 布林带
12. rsi_wilder(14)              → RSI(14)
13. build_divergences(strokes)  → 笔级背驰
14. build_divergences(segments) → 线段级背驰
15. analyze_lines_form()        → 走势形态标签
16. build_fake_bis()            → 笔内虚拟笔
17. build_signals(笔, 笔中枢, 笔背驰)    → 笔级买卖点
18. build_signals(线段, 线段中枢, 线段背驰) → 段级买卖点
19. 信号过滤（段级标记 + 盈亏比 + 趋势）
20. 段级止损映射（stop_loss_2）
21. build_action_focus()        → 当下关注点
22. td_sequential()             → TD9
23. build_chan_advanced_context() → 高级结构分析

输出: AnalyzeResponse（30+ 字段的完整响应）
```

---

## 8. 回测引擎

### 8.1 架构设计

回测引擎位于 `backtest_quick.py`，采用**信号驱动成交模型**：

```
请求 → 获取K线 → 运行完整缠论流水线 → 信号过滤管线 → 模拟交易 → 指标计算 → 响应
```

### 8.2 信号过滤管线

信号在进入模拟前经过三层过滤：

```
原始信号（笔级 + 段级）
  ↓ _apply_resonance_filter()     # 多级别共振过滤
  ↓ _apply_strategy_filter()      # Phase 1 策略过滤
  ↓ _simulate()                   # 模拟引擎
```

#### 第一层：共振过滤（`_apply_resonance_filter`）

根据高级别趋势判定（`composite`）过滤信号：

| composite | 买信号 | 卖信号 |
|-----------|--------|--------|
| `aligned_uptrend` | 全部保留 | 仅保留一类 |
| `aligned_downtrend` | 仅保留一类 | 全部保留 |
| `cross_level_divergent` | 仅保留一类 | 仅保留一类 |
| 其他 | 全部保留 | 全部保留 |

#### 第二层：策略过滤（`_apply_strategy_filter`，Phase 1 新增）

1. **信号类型过滤**：跳过 `first`（一类）和 `third_class`（类三）
   - 理由：一类信号虽理论正确但止损大、频次低；类三信号离开深度浅、可靠性差

2. **中枢内震荡过滤**：信号价格在笔中枢 [ZD, ZG] 内时不交易
   - 例外：`second_class`（类二）允许在中枢内交易（因为类二本身就定义在中枢内震荡中）

#### 第三层：仓位管理（在 `_open` 中执行）

| 信号类型 | 保证金比例 |
|----------|-----------|
| 二买 / 三买 | 全仓（100% trade_amount） |
| 二买延伸 / 类二买 | 半仓（50% trade_amount） |

### 8.3 模拟交易流程

**核心循环**：逐根 K 线遍历，按以下优先级处理：

```
对每根 K 线：
  1. 止损检查（如有持仓 + active_sl）
     - 多头: candle.low <= active_sl → 止损平仓
     - 空头: candle.high >= active_sl → 止损平仓

  2. 强平检查（leverage > 1 时）
     - 多头: candle.low <= entry × (1 - 1/lev) → 强平平仓
     - 空头: candle.high >= entry × (1 + 1/lev) → 强平平仓

  3. 信号处理
     买入信号:
       - 已有多头 → 跳过
       - 已有空头 → 平空仓 → 开多仓
       - 无仓位   → 开多仓
     卖出信号:
       - 已有空头 → 跳过
       - 已有多头 → 平多仓 → 开空仓（long_short_flip）/ 仅平仓（long_only_flip）
       - 无仓位   → 开空仓（仅 long_short_flip）
```

**开仓逻辑**（`_open`）：
- 保证金 = `min(trade_amount_usdt, balance)`（固定每笔）或全余额
- 半仓信号乘以 0.5
- 数量 = `margin × leverage / (price × (1 + fee_rate))`（扣除手续费）
- 止损 = 信号的 `stop_loss`

**平仓逻辑**（`_close`）：
- 多头 PnL = `qty × close × (1 - fee) - qty × entry`
- 空头 PnL = `|qty| × entry × (1 - fee) - |qty| × close × (1 + fee)`
- PnL 上限 = `-margin`（最多亏光保证金）
- 更新余额、权益、回撤

**退出原因**：

| reason | 含义 |
|--------|------|
| `signal` | 反向信号触发平仓 |
| `stop_loss` | 止损价被触及 |
| `liquidation` | 杠杆强平价被触及 |

### 8.4 指标计算

#### 8.4.1 往返交易（Round Trip）

每笔完整的开仓→平仓组成一个往返交易，记录：
- `entry_bar_idx` / `exit_bar_idx`
- `entry_price` / `exit_price`
- `side`（LONG / SHORT）
- `pnl_usdt` / `pnl_pct`
- `bars_held`（持仓 K 线数）
- `signal_kind_at_entry`（入场时的信号类型）

#### 8.4.2 汇总指标

| 指标 | 计算方式 |
|------|----------|
| `win_rate` | 盈利往返数 / 总往返数 |
| `profit_factor` | 总盈利 / 总亏损 |
| `expectancy` | 平均每笔 PnL |
| `max_consecutive_losses` | 最大连续亏损次数 |
| `max_drawdown_fraction` | 最大回撤（峰谷权益差 / 峰值权益） |
| `sharpe_naive` | `(mean(returns) / stdev(returns)) × sqrt(n)` |

#### 8.4.3 按信号类型统计

对每种 `signal_kind_at_entry` 分别统计交易次数、盈亏数、胜率、平均 PnL。

---

## 9. 前端图表系统

### 9.1 K 线图系列

ECharts 图表包含 **15 个数据系列**，通过 `buildChartOption()` 构建：

| # | 系列 | 类型 | 颜色 | 说明 |
|---|------|------|------|------|
| 1 | K 线 | candlestick | 涨 `#26a69a` / 跌 `#ef5350` | 含当前价黄色虚线 |
| 2 | {lv}笔 | line | 白色 `rgba(255,255,255,0.78)` | 连接笔起止价格 |
| 3 | 未完成笔 | line | 青色 `#00bcd4`，虚线 | 进行中的笔 |
| 4-7 | 分型（4个scatter） | scatter | 顶紫 `#ba68c8` / 底绿 `#66bb6a` | 含进行中分型 |
| 8 | 买点 | scatter | 绿色 `#00e676`，circle | 本级12px / 段级18px+白框 |
| 9 | 卖点 | scatter | 红色 `#ff1744`，circle | 同上 |
| 10 | 背驰点 | scatter | diamond 13px | 下行青 `#00bfa5` / 上行粉 `#f06292` |
| 11 | {lv}中枢 | markArea | 白色半透明矩形 | 本级笔中枢 |
| 12 | {hi}中枢 | markArea | 蓝色半透明矩形 | 高级别中枢（虚线边框） |
| 13 | {hi}笔（段） | line | 蓝色 `#42a5f5` | 通过插值绘制折线 |
| 14 | BOLL | 3×line | 橙色 `rgba(255,183,77,x)` | 上/中/下轨 |
| 15 | MACD | bar + 2×line | 柱图涨跌色，DIF 青/DEA 橙 | 附图1 |
| 16 | RSI14 | line | 紫色 `#ce93d8` | 附图2，70/30 超买超卖线 |
| 17-18 | 回测叠加 | scatter | 买绿 `#69f0ae` / 卖红 `#ff8a80` | 回测交易标记 |

### 9.2 信号标注规范

买卖点使用数字标注在 K 线图上：

| Kind | 标注 | 中文名 |
|------|------|--------|
| `first` | **1** | 一买/一卖 |
| `second` | **2** | 二买/二卖 |
| `third` | **3** | 三买/三卖 |
| `second_class` | **2'** | 类二买/类二卖 |
| `third_class` | **3'** | 类三买/类三卖 |
| `second_extend` | **2+** | 二买/二卖延伸 |
| `td9` | **T9** | TD9 |

**视觉区分**：
- 买点数字在 K 线**下方**（`position: "bottom"`），绿色
- 卖点数字在 K 线**上方**（`position: "top"`），红色
- 本级别（bi）：12px 圆点 + 深色细边框 + 10px 字号
- 大级别（segment）：18px 圆点 + 白色粗边框 + 12px 粗体字
- 悬停 Tooltip 显示完整标签（如"5m二买"或"30m三卖"）及精确价格

### 9.3 图层控制

11 个独立开关 + 3 个预设：

**预设**：
- **看盘**：笔 + 未完成笔 + 段 + 买卖点 + 中枢 + BOLL + RSI
- **复盘**：全部开启（除 FakeBI）
- **极简**：笔 + 未完成笔 + 段 + 买卖点 + 中枢

### 9.4 侧栏功能卡片

| Tab | 卡片 | 功能 |
|-----|------|------|
| 当下 | VerdictCard | 多空判定（启发式 + GLM AI） |
| 当下 | ActionFocusCard | 当下关注点（中枢位置、活跃笔、最近背驰/信号） |
| 当下 | SignalsCard | 最近 4 个信号详情（SL/TP/R:R） |
| 当下 | StructureStatusCard | 结构统计（笔数/线段数/中枢数等） |
| 风控 | RiskCalculator | 仓位计算器（风险比例 / 固定数量模式） |
| 风控 | PaperTradingCard | 模拟交易 |
| 风控 | DisciplineCard | 交易纪律（连续亏损计数 + 熔断） |
| 研究 | MultiTimeframeCard | 多周期并行分析 |
| 研究 | BacktestCard | 快速回测（含权益曲线图 + 交易明细表） |
| 参考 | AdvancedStructureCard | 高级结构分析（区间套、趋势递归） |
| 参考 | GlmConfigCard | GLM API 配置 |

---

## 10. 配置项说明

### 10.1 核心引擎配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `segment_engine` | `legacy` | 线段算法：`legacy`（三笔重叠延伸）或 `strict67`（特征序列标准） |
| `divergence_macd_metric` | `area` | 背驰力度对比维度 |
| `divergence_ratio` | `0.8` | 背驰判定阈值（离开/进入力度比） |
| `divergence_min_breakout_ratio` | `0.05` | 最小突破距离（相对中枢高度） |
| `fractal_include_tentative` | `True` | 是否检测进行中分型 |
| `stroke_collapse_shallow_reversal` | `True` | 是否折叠浅反向笔 |
| `stroke_collapse_middle_max_ratio` | `0.22` | 浅反向判定阈值 |
| `enable_t2s_second_extend` | `True` | 是否启用二类延伸信号 |
| `enable_standalone_second_signals` | `True` | 是否启用独立形态二类信号 |
| `enable_t1p_pan_first_signals` | `True` | 是否启用盘整一类信号 |
| `bsp1_only_multibi_zs` | `False` | 一类信号是否只从多笔中枢产生 |
| `pivot_merge_adjacent_overlaps` | `True` | 是否合并相邻重叠中枢 |

### 10.2 回测配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `backtest_max_bars` | `30000` | 回测最大 K 线数 |
| `analyze_max_bars` | `5000` | 单次分析最大 K 线数 |

### 10.3 数据源配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `binance_base_url` | `https://api.binance.com` | Binance 现货 API |
| `binance_futures_base_url` | `https://fapi.binance.com` | Binance 合约 API |
| `request_timeout_seconds` | `12.0` | HTTP 请求超时 |
| `max_klines_limit` | `1000` | 单次获取 K 线上限 |

---

## 11. 数据流总览

```
用户选择币种/周期（前端）
    ↓
POST /analyze { symbol, interval }
    ↓
AnalyzerService.analyze()
    ├── 获取低周期 K 线（BinanceRepository）
    ├── 获取高周期 K 线
    ├── project_higher_onto_base() → 高级别笔/中枢映射
    └── build_analyze_bundle()
        ├── normalize_candles()      → 标准化 K 线
        ├── find_fractals()          → 分型
        ├── build_strokes()          → 笔
        ├── build_segments()         → 线段
        ├── build_pivots()           → 笔中枢 + 线段中枢
        ├── build_divergences()      → 背驰
        ├── build_signals()          → 笔级 + 段级买卖点
        ├── 信号过滤/去重/止损映射
        ├── build_action_focus()     → 当下关注点
        ├── td_sequential()          → TD9
        └── build_chan_advanced_context() → 趋势递归/区间套
    ↓
AnalyzeResponse（JSON）
    ↓
前端 EChartsChart.buildChartOption() → 15 个数据系列渲染
前端侧栏卡片 → 信号列表/结构统计/AI 判定
```

```
回测请求（前端或 API）
    ↓
POST /backtest/quick { symbol, interval, strategy, ... }
    ↓
run_quick_backtest()
    ├── 获取 K 线
    ├── 获取高周期 K 线 → 高级别笔/中枢映射
    ├── build_analyze_bundle() → 完整缠论分析
    ├── _apply_resonance_filter()   → 多级别共振过滤
    ├── _apply_strategy_filter()    → 信号类型 + 中枢内过滤
    └── _simulate()                 → 逐 K 线模拟交易
        ├── 止损检查
        ├── 强平检查
        ├── 信号处理（开仓/平仓/反仓）
        └── 往返交易追踪
    ↓
QuickBacktestResponse { metrics, trade_log, closed_trades, stats_by_signal_kind }
```

---

## 12. 策略优化阶段

当前已实现 Phase 1，后续规划：

### Phase 1（已实现）：基础信号过滤

- 跳过一类和类三信号
- 中枢内信号回避（保留类二）
- 低置信信号（二买延伸/类二）半仓

### Phase 2（规划中）：MACD 强度门控 + 动态止损

- MACD 面积比低于阈值的信号进一步过滤
- 中枢边界作为辅助止损参考
- 多级别共振增强

### Phase 3（规划中）：自适应参数

- 根据波动率动态调整中枢内过滤阈值
- 根据近期胜率动态调整仓位比例

### 验证标准

使用固定的 20 个时间段（`random.seed(42)` 生成），7-60 天不等，覆盖 5m/15m/30m/4h 四个周期：

| 目标指标 | 目标值 |
|----------|--------|
| 盈利段占比 | >= 65% |
| 平均 Sharpe | >= 0.5 |
| 平均胜率 | >= 55% |
| 平均最大回撤 | <= 3%（20x 杠杆） |

---

*本文档基于代码实际实现撰写，覆盖后端引擎、前端展示、信号策略、回测系统的完整技术细节。*
