# 图表指标与视觉优化

> 分支：`feat/optimize-kline-indicators`
> 讨论日期：2026-05-05

---

## 1. 图层精简

### 1.1 BOLL 合并为单一开关

**现状**：图层开关中 BOLL 对应三个 ECharts series（上轨/中轨/下轨），通过 `LAYER_SERIES_MAP` 中的 `showBoll: ["BOLL上", "BOLL中", "BOLL下"]` 批量控制。

**问题**：用户无法单独开关某一条轨（也不需要），三条轨作为一个整体才有意义——布林带本质是一个波动率通道。

**改动**：
- 保留 `showBoll` 图层键不变（一个开关控制三条线）
- 去掉前端 legend 中的三个独立图例项，合并为单个 `BOLL` 图例
- 或者保持三条 series 但 legend 中只展示一个 `BOLL` 入口（点击联动三条）

### 1.2 删除「笔停顿」图层

**现状**：`showBiPause` 独立控制一组 scatter 标记，标注收盘价突破笔端点的位置（`biPauseScatter`）。

**问题**：笔停顿只是一个辅助观察，不是缠论标准构件。笔端点本身已经清晰可辨，额外的 scatter 标记增加视觉噪声而不提供结构信息。

**改动**：
- 删除 `showBiPause` 图层键
- 删除 `layer-presets.ts` 中所有涉及 `showBiPause` 的条目
- 删除 `chart-options/index.ts` 中的 `biPauseScatter` 函数及其调用
- 删除 `chart-palette.ts` 中的 `pause` / `pauseBorder` 颜色

### 1.3 删除「上级笔」与「上级中枢」图层

**现状**：
- `showBisLv2` 控制 `bis_lv2`（上级周期独立计算的笔，映射回本级时间轴）
- `showZhongshuLv2` 控制 `zhongshus_lv2`（上级周期独立计算的中枢）

**背景**：系统已有"线段"和"线段中枢"，它们由本级笔通过特征序列分型递归生成，在缠论定义上就是"更高级别的走势构件"。上级笔/上级中枢是从更大周期 K 线独立跑完整流水线再映射回来的，两者在大部分情况下几何接近，功能重复。

**去掉的原因**：
1. 线段与本级 K 线严格索引对齐，比"上级笔映射"更可靠
2. 图表上同时存在线段和上级笔会造成视觉冗余和混乱
3. 缠论实战中两级联立（本级笔+线段）已足够；若需第三级，应切换到更高级别周期查看

**改动**：
- 删除 `showBisLv2` / `showZhongshuLv2` 图层键
- 删除 `layer-presets.ts` 中所有涉及这两个键的条目
- 删除 `chart-options/index.ts` 中 `strokeLine("上级笔", ...)` 和 `pivotBand("上级中枢", ...)` 的调用
- 删除 `chart-palette.ts` 中的 `higherBi` / `pivotHigher` 颜色
- **后端不动**：`analyzer.py` 中的 `HIGHER_INTERVAL` 映射和 `project_higher_onto_base` 仍保留（区间套等进阶结构可能使用），只是前端图表不再展示这两组数据

### 1.4 图层键变更汇总

| 删除 | 保留 | 备注 |
|---|---|---|
| `showBiPause` | `showBis` | 本级笔 |
| `showBisLv2` | `showActiveBi` | 未完成笔 |
| `showZhongshuLv2` | `showSegments` | 线段 |
| | `showFractals` | 分型 |
| | `showSignals` | 买卖点 |
| | `showDivergences` | 背驰点 |
| | `showZhongshu` | 笔中枢带 |
| | `showZhongshuSeg` | 线段中枢带 |
| | `showBoll` | BOLL（合并图例） |
| | `showRsi` | RSI |
| | `showFakeBi` | FakeBI |

---

## 2. 级别映射补全

### 2.1 补充 15 分钟 → 1 小时

**现状**：后端 `analyzer.py` 中 `HIGHER_INTERVAL` 缺少 `"15": "60"`，导致 15 分钟周期分析时拉不到上级 K 线，区间套等进阶结构为空。

**改动**：
```python
HIGHER_INTERVAL = {
    "1": "5",
    "5": "30",
    "15": "60",    # ← 新增
    "30": "240",
    "240": "1440",
    "1440": "10080",
    "10080": "43200",
}
```

### 2.2 级别对应关系（完整）

| 本级周期 | 上级周期（线段≈上级笔） |
|---|---|
| 1 分钟 | 5 分钟 |
| 5 分钟 | 30 分钟 |
| 15 分钟 | 1 小时 |
| 30 分钟 | 4 小时 |
| 4 小时 | 1 天 |
| 1 天 | 1 周 |
| 1 周 | 1 月 |

---

## 3. 颜色与线型方案

### 3.1 新配色

| 元素 | 旧颜色 | 新颜色 | 说明 |
|---|---|---|---|
| 本级笔 | 金黄 `rgba(255,209,92,0.78)` | 白色 `rgba(255,255,255,0.78)` | 本级别结构 |
| 笔中枢带 | 紫色透明 `rgba(171,71,188,0.38)` | 白色透明 `rgba(255,255,255,0.12)` | 同级笔中枢 |
| 线段 | 橙色 `#ffa726` | 蓝色 `#42a5f5` | 更高级别结构 |
| 线段中枢带 | 橙色透明 `rgba(255,152,0,0.34)` | 蓝色透明 `rgba(66,165,245,0.18)` | 同级线段中枢 |

### 3.2 线宽统一

**现状**：笔宽 2，线段宽 4（且线段有 `shadowBlur: 10` 发光效果）。

**改动**：
- 笔与线段统一宽度（建议 **1.5** 或 **2**）
- 线段去掉 `shadowBlur` 发光效果，与笔视觉权重一致
- 通过颜色区分级别，而非粗细

### 3.3 配色逻辑

缠论的自同构性意味着"笔→中枢"的递归关系在每个级别上都相同。用两套颜色对应两个级别：

- **白色系**：本级笔 + 本级笔中枢（白线 + 白色半透明带）
- **蓝色系**：线段 + 线段中枢（蓝线 + 蓝色半透明带）

---

## 4. 回测卡片重构

### 4.1 参数设计原则

- **用户只需填写核心参数**：投入金额、杠杆、时间范围
- 品种和周期跟随当前页面，无需选择
- 每笔保证金由投入金额自动计算，不单独暴露
- 手续费固定 10 bps，不暴露为输入项
- 策略固定"多空"（`long_short_flip`），不暴露为选择项

### 4.2 参数一览

| 参数 | 控件 | 默认值 | 说明 |
|---|---|---|---|
| 品种 | **跟随页面** | 当前 `symbol` | 无选择器 |
| 周期 | **跟随页面** | 当前 `interval` | 无选择器 |
| 投入金额 | 数字输入 | **10000** USDT | 对应后端 `initial_equity_usdt` |
| 杠杆 | 数字输入 | **1** | 范围 1–100，对应后端 `leverage` |
| 每笔保证金 | **自动计算** | `投入金额 × 10%` | 不暴露为输入项；对应后端 `trade_amount_usdt` |
| 手续费 | **固定** | 10 bps | 不暴露为输入项；对应后端 `fee_bps` |
| 策略 | **固定** | `long_short_flip`（多空） | 不暴露为选择项 |
| 开始时间 | `datetime-local` | **当前时间 - 30 天** | ISO 格式，转 `start_time_ms` 传给后端 |
| 结束时间 | `datetime-local` | **当前时间** | 不填则到最新 K 线 |

### 4.3 每笔保证金计算规则

```
trade_amount_usdt = initial_equity_usdt × 10%
```

- 投入 10000U → 每笔 1000U 保证金
- 投入 5000U → 每笔 500U 保证金
- 最小值下限：10U（避免保证金过小无法开仓）
- 此计算在前端完成，直接传 `trade_amount_usdt` 给后端

### 4.4 默认时间范围

- 开始时间：页面加载时取 `new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 16)` 填入 `datetime-local` 输入框
- 结束时间：页面加载时取 `new Date().toISOString().slice(0, 16)` 填入
- 用户可手动修改；后端不要求必填（不传则自动拉取全部/最新）

### 4.5 输入控件（最终）

用户实际看到的表单：

| 控件 | 类型 | 说明 |
|---|---|---|
| 投入金额 (USDT) | 数字输入 | 默认 10000 |
| 杠杆 | 数字输入 | 默认 1，范围 1–100 |
| 开始时间 | datetime-local | 默认 30 天前 |
| 结束时间 | datetime-local | 默认当前时间 |

**已删除的控件**：品种选择器、周期选择器、每笔保证金、手续费、策略选择器。

### 4.6 结果展示重构

### 4.3 结果展示重构

#### 4.3.1 权益折线图

在结果顶部添加小型权益曲线：

- 数据源：后端 `trade_log` 中每笔交易的 `equity_after`
- 图表类型：**阶梯线**（`step: "middle"`），只在交易点标注权益，无交易的 K 线区间权益不变
- X 轴：交易序号或时间
- Y 轴：USDT 权益
- 可用小型 ECharts 实例（高度约 120px），不依赖主图

#### 4.3.2 交易明细表格

用 HTML 表格替代当前的纯文本 `<details>` 列表：

| 列 | 字段 | 来源 |
|---|---|---|
| # | 序号 | 自增 |
| 方向 | LONG / SHORT | `QuickBacktestRoundTrip.side` |
| 买入时间 | `entry_time` | 已有 |
| 买入价 | `entry_price` | 已有 |
| 卖出时间 | `exit_time` | 已有 |
| 卖出价 | `exit_price` | 已有 |
| 盈亏金额 | `pnl_usdt` | 已有，正数绿色，负数红色 |
| 持仓时间 | `bars_held` | 已有（需换算为可读时间，如 "3h30m"） |
| 信号类型 | `signal_kind_at_entry` | 已有（一类/二类/三类等） |
| 平仓原因 | exit_reason | 从 `trade_log` 中匹配（signal / stop_loss / liquidation） |

后端 `closed_trades`（`QuickBacktestRoundTrip`）已包含 `entry_time/exit_time/pnl_usdt/bars_held/side/signal_kind_at_entry`，数据完整。`exit_reason` 需从 `trade_log` 中对应平仓条目获取。

表格样式：
- 固定表头，内容可滚动（`max-height: 240px, overflow-y: auto`）
- 盈亏金额列：正值 `text-success`，负值 `text-danger`
- 行高紧凑（`text-[11px]`）

#### 4.3.3 汇总指标

保留现有指标面板，在表格下方展示：

- K 线根数、总收益（%）、最大回撤（%）、最终权益
- 交易次数、胜率、盈亏比（profit factor）、Sharpe
- 止损触发次数

### 4.4 后端数据充分性

后端 `QuickBacktestResponse` 已包含回测所需全部数据：

```
metrics: bars_used, trades, final_equity_usdt, total_return_fraction,
         max_drawdown_fraction, sharpe_naive, win_rate, profit_factor,
         expectancy_per_trade_usdt, max_consecutive_losses, stop_loss_hits

trade_log: QuickBacktestTrade[]（每笔开仓/平仓，含 equity_after）

closed_trades: QuickBacktestRoundTrip[]（完整回合，含 entry/exit/pnl/bars_held）

stats_by_signal_kind: 按信号类型分类统计
```

**后端无需改动**，所有调整集中在前端回测卡片的 UI 重构。

---

## 5. 前端级别感知与标注

### 5.1 背景

当前前端只知道用户选了哪个周期（interval），不知道"上级周期是什么"。图表图例和图层开关使用静态中文标签（"本级笔"、"线段"、"笔中枢带"、"线段中枢带"），不反映实际周期级别。

缠论自同构性意味着两级联立（本级笔 + 线段）即可覆盖两个级别。为了让用户直观知道图表上每一层结构对应什么级别，前端需要一份与后端同步的级别映射表。

### 5.2 新增 HIGHER_INTERVAL 常量

在 `constants/` 下新增前端级别映射，与后端 `analyzer.py` 保持同步：

```typescript
// 与后端 HIGHER_INTERVAL 保持同步
export const HIGHER_INTERVAL: Record<string, string> = {
  "1": "5",
  "5": "30",
  "15": "60",
  "30": "240",
  "240": "1440",
  "1440": "10080",
  "10080": "43200",
};
```

### 5.3 新增 INTERVAL_LABEL 常量

统一周期 → 可读标签的映射（当前散落在 `multi-timeframe-card.tsx` 的局部函数中）：

```typescript
export const INTERVAL_LABEL: Record<string, string> = {
  "1": "1m", "5": "5m", "15": "15m", "30": "30m",
  "60": "1h", "240": "4h", "1440": "1d",
  "10080": "1w", "43200": "1M",
};
```

### 5.4 图例与图层标签动态化

图例和图层开关的标签从静态中文改为带实际周期级别的动态标签。

**规则**：
- 本级（bi）结构 → `{interval}笔` / `{interval}中枢`
- 线段级（segment）结构 → `{higherInterval}笔` / `{higherInterval}中枢`

**示例（用户选 5m 时）**：

| 旧标签 | 新标签 | 说明 |
|---|---|---|
| 本级笔 | 5m笔 | 白色，5分钟级别笔 |
| 未完成笔 | 5m未完成笔 | 白色虚线 |
| 线段 | 30m笔 | 蓝色，线段≈30分钟笔 |
| 笔中枢带 | 5m中枢 | 白色半透明 |
| 线段中枢带 | 30m中枢 | 蓝色半透明 |

**注意**：图层开关的 `label`（如"本级笔"）和 `tip`（如"分型确认之后的定向折线"）也需同步更新为动态标签，tooltip 保持解释性文字但加上级别前缀。

**实现要点**：
- `layer-toggles.tsx` 的 `LAYER_GROUPS` 目前是静态常量，需改为接收 `interval` 参数的函数或 hook，根据当前 interval 和 `HIGHER_INTERVAL` 动态生成标签
- `chart-options/index.ts` 的 series `name` 需从静态字符串改为动态拼接
- `layer-presets.ts` 的 `LAYER_SERIES_MAP` 的值（series name 列表）也需要动态化，因为 legend 选中状态依赖 series name 匹配

### 5.5 周期选择器标注上级

`toolbar-primary.tsx` 的周期选择器旁，显示当前上级周期提示：

```
5m  ·  上级 → 30m
```

用户点击可直接切换到上级周期（可选功能，优先级低）。

---

## 6. 买卖点级别标注

### 6.1 背景

后端 Signal 模型已有 `level` 字段：

```python
level: Literal["bi", "segment", "higher_bi"] = "bi"
```

前端 TypeScript `Signal` 类型缺失此字段。信号在图表上只显示"买点"/"卖点"符号，不标注级别和类型。

### 6.2 前端 Signal 类型补全

在 `types/analysis.ts` 的 `Signal` 接口中新增：

```typescript
export interface Signal {
  // ... 现有字段 ...
  level?: "bi" | "segment" | "higher_bi";  // 新增
  pivot_level?: "bi" | "segment" | null;    // 新增
}
```

### 6.3 买卖点图表标注设计

#### 6.3.1 标注格式

图表上每个买卖点用 **彩色数字** 标注，颜色区分买/卖，数字区分类型：

| kind | 含义 | 图表标注 |
|---|---|---|
| `first` | 一买 / 一卖 | `1` |
| `second` | 二买 / 二卖 | `2` |
| `third` | 三买 / 三卖 | `3` |
| `second_class` | 类二买 / 类二卖 | `2'` |
| `third_class` | 类三买 / 类三卖 | `3'` |
| `second_extend` | 二买延伸 / 二卖延伸 | `2+` |
| `td9` | TD9 | `T9` |

颜色规则：
- **买点**：绿色数字（使用 `signalBuy` 颜色）
- **卖点**：红色数字（使用 `signalSell` 颜色）

示例：绿色 `2` = 二买，红色 `3'` = 类三卖，绿色 `2+` = 二买延伸

#### 6.3.2 级别区分（bi vs segment）

同一张图表上有两个级别的信号。通过 **大小 + 加粗 + 边框** 区分：

| | bi 级（本级） | segment 级（更高级别） |
|---|---|---|
| symbolSize | 14 | 20 |
| 标注字号 | 10px，fontWeight 400（普通） | 12px，fontWeight 700（**加粗**） |
| 边框 | 1.5px | 2.5px，白色 borderColor |
| 图表标注 | 绿色/红色数字 | 绿色/红色数字，加粗加大 |

**设计理由**：
- 大 + 粗 + 粗边框 = 更高级别，视觉权重直觉对应级别重要性
- 保持颜色和数字体系一致（1/2/3），不增加新符号的认知负担
- 图表空间有限，短数字比文字标注更紧凑

#### 6.3.3 Tooltip 完整标注

Hover 时 tooltip 显示完整级别信息：

```
5m二买
价格: 67234.50
```

或：

```
30m类三卖
价格: 67234.50
```

级别周期映射：
- `level === "bi"` → `INTERVAL_LABEL[interval]`（如 5m 页面 → "5m"）
- `level === "segment"` → `INTERVAL_LABEL[HIGHER_INTERVAL[interval]]`（如 5m 页面 → "30m"）

#### 6.3.4 KIND 标注映射

新增短标注映射（图表数字）：

```typescript
export const KIND_CHART_LABEL: Record<string, string> = {
  first: "1", second: "2", third: "3",
  second_class: "2'", third_class: "3'",
  second_extend: "2+", td9: "T9",
};
```

新增带方向的完整标注（tooltip 用）：

```typescript
export const KIND_BUY_NAME: Record<string, string> = {
  first: "一买", second: "二买", second_extend: "二买延伸",
  third: "三买", second_class: "类二买", third_class: "类三买", td9: "TD9",
};
export const KIND_SELL_NAME: Record<string, string> = {
  first: "一卖", second: "二卖", second_extend: "二卖延伸",
  third: "三卖", second_class: "类二卖", third_class: "类三卖", td9: "TD9",
};
```

---

## 7. 涉及文件（完整）

### 前端
| 文件 | 改动 |
|---|---|
| `constants/chart-palette.ts` | 更新 bi / segment / pivotBi / pivotSegment 颜色，删除 pause / pauseBorder / higherBi / pivotHigher |
| `constants/layer-presets.ts` | 删除 showBiPause / showBisLv2 / showZhongshuLv2 键，更新 DEFAULT_LAYERS 和预设 |
| `constants/level-maps.ts`（新增） | HIGHER_INTERVAL 映射、INTERVAL_LABEL 映射、KIND_BUY_NAME / KIND_SELL_NAME |
| `components/chart/chart-options/index.ts` | 删除上级笔/上级中枢 series，统一线宽；series name 动态化（传入 interval）；signalScatter 显示级别+类型标注；按 level 区分 symbol 样式 |
| `components/toolbar/layer-toggles.tsx` | 删除笔停顿/上级笔/上级中枢 toggle 项；标签动态化（"5m笔"、"30m笔"） |
| `components/toolbar/toolbar-primary.tsx` | 周期选择器旁标注上级周期 |
| `components/sidebar/backtest-card.tsx` | 精简为 4 个输入（投入金额、杠杆、开始/结束时间）；每笔保证金自动算 10%；手续费/策略固定；默认时间 30 天 |
| `types/analysis.ts` | Signal 接口新增 `level`、`pivot_level` 字段 |

### 后端
| 文件 | 改动 |
|---|---|
| `services/analyzer.py` | HIGHER_INTERVAL 补充 `"15": "60"` |

### 不需要改后端的理由
- Signal 的 `level` 字段后端已返回（`"bi"` / `"segment"` / `"higher_bi"`），前端只需补全 TS 类型声明
- 买卖点类型（`kind`）后端已返回（`first` / `second` / `third` 等）
- 前端根据 `level` + 当前 `interval` + `HIGHER_INTERVAL` 映射即可计算出级别标签

---

## 8. 策略优化——提升胜率

> 基于基线回测结果（50% 胜率、26.6% 止损率），结合缠论理论提出以下优化方向。
> 使用 `docs/BACKTEST_BASELINE.md` 中固定的 20 个时间段做前后对照。

### 8.1 信号类型过滤

**现状**：所有信号类型（一买/二买/三买/类二买/类三买/TD9）同等对待，全部开仓。

**优化**：不做一类买卖点，按优先级决定是否开仓和仓位比例。

| 优先级 | 类型 | 结构特征 | 操作 |
|---|---|---|---|
| 1 | 三买/三卖 | 离开中枢后回测不进中枢 | **标准仓位**——趋势已确认，结构最清晰 |
| 2 | 二买/二卖 | 反转后回测抬高低点/压低高点 | **标准仓位**——二次确认反转 |
| 3 | 二买延伸 | 同中枢语境下再次抬高低点 | **半仓**——二买的强化版 |
| 4 | 类二买/类二卖 | 中枢震荡中抬高低点 | **半仓**——保留，但中枢内风险较高 |
| - | 一买/一卖 | 趋势背驰末端 | **不交易**——判断难度高，容易接飞刀 |
| - | 类三买/类三卖 | 浅离开中枢 | **不交易**——离开力度不足，假突破概率高 |
| - | TD9 | TD Sequential 9 计数 | **辅助参考**，不作为独立开仓信号 |

**仓位规则**：
- 标准仓位 = 投入金额 × 10%（与当前回测一致）
- 半仓 = 投入金额 × 5%
- 后端 `trade_amount_usdt` 根据信号 `kind` 动态计算

### 8.2 避开中枢内震荡

**现状**：价格在中枢 [ZD, ZG] 范围内也会触发信号并开仓，这类信号大部分是噪声。

**优化**：除类二买/类二卖外（按 §8.1 保留），其他信号类型在中枢内部时不开仓。

**规则**：
- 当前价格在某笔中枢 [ZD, ZG] 内 → 跳过该信号（类二除外）
- 当前价格在所有笔中枢之外 → 正常开仓
- 判断方式：检查信号 `idx` 对应的价格是否落入最近一个笔中枢的价格区间

**预期效果**：这是减少亏损交易最有效的一步。基线中 26.6% 的止损触发很大一部分来自中枢内震荡。

### 8.3 区间套（多级别共振）

**现状**：bi 级和 segment 级信号独立触发，不考虑趋势方向是否一致。

**优化**：本级别信号只在与更高级别趋势方向一致时才开仓。

**规则**：
- bi 级买点 → 检查 segment 级趋势是否偏多（最近线段方向向上 或 最近线段中枢向上扩展）
- bi 级卖点 → 检查 segment 级趋势是否偏空
- segment 级信号不受此限制（它本身就是更高级别信号）

**实现**：后端 `action_focus.higher_pivot` 和 `advanced_context.segment_trend_runs` 已包含上级趋势信息，可用于判断。

### 8.4 力度确认闸门

**现状**：背驰信号的 `macd_ratio` 不做过滤，弱背驰和强背驰同等对待。

**优化**：只接受 MACD 力度明确减弱的信号。

**规则**：
- `macd_ratio < 0.8`（离开段力度 < 进入段力度的 80%）时才接受背驰类信号
- 可通过后端参数 `divergence_ratio`（当前默认 0.8）控制
- 前端可增加闸门参数，或直接调后端配置

### 8.5 止损优化

**现状**：止损设在笔级最近分型高/低点，偏紧。

**优化**：

| 信号级别 | 止损位置 | 说明 |
|---|---|---|
| bi 级二买/三买 | 笔中枢 ZD（买）/ ZG（卖） | 用中枢边界代替分型点，空间更大 |
| bi 级类二买 | 笔级分型点（保持当前） | 类二本身风险较高，保持紧止损 |
| segment 级信号 | segment 级笔中枢边界 | 级别对应 |

**动态止损**（可选，优先级低）：
- 价格运行 1R（1 倍风险）后将止损移到成本价

### 8.6 优化优先级与实施路径

| 阶段 | 优化项 | 改动位置 | 预期效果 |
|---|---|---|---|
| **Phase 1** | 信号类型过滤（不做一类、不做类三） | 后端 `build_signals` 或回测引擎 | 交易次数 ↓，信号质量 ↑ |
| **Phase 1** | 避开中枢内震荡 | 后端信号过滤 / 回测引擎 | 止损触发率 ↓ |
| **Phase 2** | 区间套（多级别共振） | 后端信号过滤 | 逆势交易 ↓ |
| **Phase 2** | 力度确认闸门 | 后端参数调整 | 弱信号过滤 |
| **Phase 3** | 止损优化（中枢边界止损） | 后端止损计算 | 假止损 ↓ |
| **Phase 3** | 仓位管理（信号类型 → 仓位比例） | 后端回测引擎 | 风险优化 |

**Phase 1 完成后应重跑 20 段回测**，与基线对比胜率和 Sharpe 的变化。

### 8.7 回测验证标准

每次优化后，使用 `docs/BACKTEST_BASELINE.md` 中相同的 20 个时间段、相同品种（BTCUSDT）进行回测。

**对比指标**：

| 指标 | 基线（1x） | 目标 |
|---|---|---|
| 盈利段占比 | 50% | ≥ 65% |
| 平均 Sharpe | +0.04 | ≥ 0.5 |
| 平均胜率 | ~48% | ≥ 55% |
| 止损触发率 | 26.6% | ≤ 20% |
| 平均总收益 | +0.04% | > 0% |
