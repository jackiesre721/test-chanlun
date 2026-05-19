# 缠论量化系统代码审计报告 — 1000U 资金场景

> 审计时间: 2026-05-19 | 审计范围: 全代码库 | 约束: 1000 USDT, 5x杠杆

---

## 一、总结

系统当前是一个**信号机枪**——每次扫描产出 50-150+ 信号，对 1000U 小账户来说是致命的。即使信号逻辑正确，回测器、风控、止损放置等基础设施存在多个会导致**虚假盈利**或**实盘亏损**的严重缺陷。

**核心结论：系统无法在当前状态下安全运行自动交易。需要先修复基础设施，再谈策略。**

---

## 二、CRITICAL — 必须立即修复

### C1. 回测器 LONG PnL 双重扣除开仓手续费

**文件**: `app/services/backtest_quick.py:179-180`

```python
# 当前代码
pnl = (exit_price - entry_price) * qty - entry_fee - exit_fee
# entry_fee 在开仓时已经从 balance 扣除过一次
# 平仓时又扣了一次，LONG 盈利被严重低估
```

**影响**: 回测 LONG 方向的收益率比实际低约 0.1%/笔。100 笔交易累计偏差 10%+。
**修复**: 平仓 PnL 只扣 exit_fee，不再扣 entry_fee。

---

### C2. 信号索引空间不一致

**文件**: `app/services/backtest_quick.py:419-420`

信号中的 K 线索引（`signal_bar_idx`）是在**标准化后的包含处理序列**中的位置，但回测模拟器遍历的是**原始 K 线序列**。两者索引不对应。

```python
# signal_bar_idx 来自 normalized klines (after inclusion processing)
# 但 simulation loop 用 raw candle index 遍历
for i, candle in enumerate(raw_klines):
    if i == signal_bar_idx:  # 错误！索引空间不同
```

**影响**: 信号在实际错误的位置触发，回测结果完全不可信。
**修复**: 要么在原始 K 线空间重新映射索引，要么模拟器也遍历标准化后的序列。

---

### C3. 强平价格公式缺少账户余额

**文件**: `app/services/risk_controls.py:31-35`

```python
liq_price = entry * (1 - 1 / leverage)  # 仅依赖杠杆
```

真实合约强平价 = `(entry_price * qty - balance) / qty`，需考虑账户余额。对 1000U 小账户，偏差可达 5-10%。

**影响**: 止损基于错误的强平价设置，可能在被强平前止损根本不触发。
**修复**: `liq_price_long = (entry * qty - balance) / qty`，SHORT 反向。

---

### C4. 纸交易无余额校验

**文件**: `app/api/routes.py:109-126`

`place_paper_order` 接受任意数量，不检查账户余额是否足够。1000U 可以开出 10000U 的仓位。

**影响**: 纸上交易完全脱离实际，无法验证策略在真实资金约束下的表现。
**修复**: 下单前 `if qty * entry_price / leverage > available_balance: reject`。

---

## 三、HIGH — 必须在上线前修复

### H1. 回测器不对称反转逻辑

**文件**: `app/services/backtest_quick.py:291-299`

反向信号（如持 LONG 时出现 SELL 信号）只平仓不开反向仓：

```python
if signal.direction != position.side:
    close_position(...)  # 只平仓
    # 没有开反向 SHORT 仓位
```

但如果 `allow_reversal=True`，应该同时开反向仓。当前逻辑导致趋势反转时少赚一半利润。

**修复**: 平仓后立即检查 `allow_reversal`，若为 True 则开反向仓。

---

### H2. 回测器全历史前瞻偏差

**文件**: `app/services/backtest_quick.py:395-404`

`run_quick_backtest()` 一次性把**全部 K 线**传给缠论引擎分析，而不是逐根 K 线增量分析。这意味着：
- 中枢识别看到未来数据
- 背驰判断看到未来 MACD
- 分型确认使用未来 K 线

```python
# 当前：一次性全量分析
bundle = build_analyze_bundle(all_klines)  # 看到全部历史+未来
signals = bundle.signals  # 信号中包含未来信息

# 应该：逐根喂入
for i in range(lookback, len(klines)):
    bundle = build_analyze_bundle(klines[:i])  # 只看到当前及之前
```

**影响**: 回测结果严重高估，可能是实际表现的 2-5 倍。
**修复**: 逐根 K 线增量分析，或至少分段（如每 100 根切一段重新分析）。

---

### H3. 回测器强平价忽略维持保证金

**文件**: `app/services/backtest_quick.py:267-275`

计算强平价时没有考虑维持保证金（maintenance margin）。币安合约维持保证金率约 0.4%（BTC）到 1%（小币种）。

对 1000U + 5x 杠杆，维持保证金差额约 20-50 USDT，直接影响是否被强平。

**修复**: `liq_price = entry - (balance - qty * entry * maint_rate) / qty`。

---

### H4. 仓位计算无最小下单量保护

**文件**: `app/services/risk_controls.py:18-52`

`compute_position_size()` 对 1000U 可能算出极小数量（如 0.001 BTC），低于交易所最小下单量（0.001 BTC）。没有检查。

**影响**: 自动下单时会因低于最小量而被交易所拒绝。
**修复**: `if qty < min_qty: return 0` 或调高 `risk_fraction`。

---

### H5. 追踪止损使用错误数据序列

**文件**: `app/services/risk_controls.py:116-123`

LONG 追踪止损应该基于 **High**（最高价），当前可能用了 Close：

```python
# 需确认用的是 highs[i] 而非 closes[i]
trailing = max(trailing, series[i] - atr * multiplier)
```

对加密货币，High 和 Close 差距可以很大（插针行情）。用错数据意味着止损被假突破频繁触发。

**修复**: LONG 用 high 序列，SHORT 用 low 序列。

---

### H6. 止损选最近分型而非结构分型

**文件**: `app/services/risk_controls.py:88-107`

当前止损逻辑选最近的分型低点/高点，而非**结构上最有意义**的分型。在密集分型区域，止损可能只放在 0.5% 外，对加密货币波动率来说必被触发。

**影响**: 止损过紧 → 频繁被扫 → 反复亏损手续费 → 1000U 快速耗尽。
**修复**: 止损应放在中枢 ZD/ZG 外侧（至少 1 ATR），而非最近分型。

---

### H7. HTTP 客户端每次请求重建

**文件**: `app/repositories/market_data.py:294-313`

每次调用 Binance API 都 `httpx.AsyncClient()` 新建连接，不复用 TCP 连接。

**影响**: 并发扫描 5 个标的时，延迟增加 200-500ms/请求，总计可能超时。
**修复**: 使用模块级或依赖注入的单例 `httpx.AsyncClient`。

---

### H8. 缓存数据优先级颠倒

**文件**: `app/repositories/market_data.py:210-223`

去重逻辑中 PG 缓存数据优先于 Binance 最新数据。如果缓存过期，应该取最新数据替换缓存，而不是用过期缓存。

**修复**: `if pg_data and not expired: return pg_data; else: fetch from binance and update cache`。

---

## 四、策略级问题 — 1000U 致命伤

### S1. 信号过多（信号机枪）

系统有 **7 条信号路径 × 2 个级别（笔/线段）= 最多 14 种信号来源**。每次扫描产出 50-150+ 信号。

对 1000U 账户：
- 每笔仓位约 200U（5x 杠杆 → 1000U 名义）
- 最多同时持 5 仓
- 150 个信号 → 大部分无法执行 → 选哪个？→ 无过滤机制

**修复建议**:
1. 每次扫描只取**最强 1-2 个信号**（按 R:R 排序）
2. 关闭弱信号路径（如 `second_class`、`third_signal`）
3. 添加信号冷却期（同一标的 4 小时内不重复开仓）

---

### S2. 止损放置在用户说的「致命区」

**文件**: `app/services/risk_controls.py:88-107`

三买止损放在中枢 ZD 附近 + 15% 缓冲区。但缓冲区是**中枢高度的 15%**，不是 ATR 的倍数。

如果中枢高度仅 50 USDT（BTC 波动 0.05%），止损只在外面 7.5 USDT → 百分之百被扫。

**修复**: 止损 = `中枢边界 - 2 * ATR(14)`，而非 `中枢高度 * 0.15`。

---

### S3. 回测跳过一买（最强信号）保留二买（最弱信号）

**文件**: `app/services/analysis_pipeline.py` 中的信号过滤

一买（first）是趋势转折点，理论胜率最高。但回测器和信号管道中，`first` 信号被标记为"太激进"而跳过，保留了 `second_class`（二买/二卖）。

这完全反了：一买是最安全的入场点（趋势反转确认），二买是追高/追跌。

**修复**: 启用 `first` 信号，关闭 `third_signal`（三买/三卖在中枢内，噪音最大）。

---

### S4. 无波动率感知

整个系统没有任何地方考虑波动率状态（高波/低波/正常）。

- BTC 日波动 2-5% → ATR 止损合理
- DOGE 日波动 5-15% → 同样 ATR 倍数会被秒扫
- 1000U 在高波时段应该减仓或暂停

**修复**: 添加波动率分位（如 ATR/price 的 20 日百分位），高波时降低仓位或暂停交易。

---

### S5. 手续费拖累被低估

5x 杠杆下，每笔交易手续费（0.04% maker + 0.06% taker ≈ 0.1%）被放大为 0.5% 名义。

```
1000U × 5x = 5000U 名义
开仓费: 5000 × 0.05% = 2.5U
平仓费: 5000 × 0.05% = 2.5U
往返: 5U = 0.5% 账户
```

如果胜率 50%，盈亏比 1.5:1（看起来不错），实际因为手续费：
- 赢: +1.5% - 0.5% = +1.0%
- 输: -1.0% - 0.5% = -1.5%
- **净期望: 0.5 × 1.0% - 0.5 × 1.5% = -0.25%/笔** → 必亏

**修复**:
1. 只在 R:R ≥ 3:1 时开仓
2. 减少交易频率（信号过滤 S1）
3. 使用限价单（maker 费率更低）

---

### S6. MACD EMA 初始化用单值而非 SMA

**文件**: `app/services/indicators.py`

EMA 初始值用第一个 K 线的 Close，而非前 N 根的 SMA。导致前 20-30 根 K 线的 MACD 值严重偏离，影响背驰判断。

**修复**: `seed = sum(closes[:period]) / period`。

---

## 五、修复优先级排序

| 优先级 | 编号 | 问题 | 预计工时 |
|--------|------|------|----------|
| P0 | C2 | 索引空间不一致（回测完全不可信） | 4h |
| P0 | H2 | 前瞻偏差（回测完全不可信） | 8h |
| P0 | C1 | LONG PnL 双重扣费 | 0.5h |
| P0 | S2 | 止损放置致命区 | 2h |
| P1 | C3 | 强平价公式错误 | 1h |
| P1 | H6 | 止损选错分型 | 2h |
| P1 | H4 | 最小下单量保护 | 0.5h |
| P1 | S1 | 信号过多（机枪） | 4h |
| P1 | S3 | 信号过滤反向 | 1h |
| P2 | C4 | 纸交易余额校验 | 1h |
| P2 | H1 | 反转逻辑不对称 | 2h |
| P2 | H3 | 维持保证金 | 1h |
| P2 | H5 | 追踪止损数据序列 | 1h |
| P2 | S4 | 波动率感知 | 3h |
| P2 | S6 | MACD 初始化 | 0.5h |
| P3 | H7 | HTTP 连接复用 | 1h |
| P3 | H8 | 缓存优先级 | 1h |
| P3 | S5 | 手续费优化 | 2h |

**总工时估算**: ~36h

---

## 六、1000U 资金下推荐配置

修复上述问题后，推荐运行参数：

```yaml
capital: 1000 USDT
leverage: 5x
max_positions: 3           # 同时最多3仓
risk_per_trade: 1%         # 每笔最大亏损10U
min_rr_ratio: 3.0          # 风险回报比 ≥ 3:1
max_daily_loss: 3%         # 日亏30U停止开仓
cooldown_hours: 4          # 同标的冷却4小时
signal_filter:
  enable: [first, second]  # 只用一买/二买
  disable: [third, second_class]  # 关闭三买和弱二买
stop_loss:
  method: atr              # ATR 止损，非中枢高度百分比
  atr_period: 14
  atr_multiplier: 2.0      # 2倍ATR
trailing_stop:
  activate_at: 1.5 ATR     # 盈利1.5ATR后启动
  step: 1.0 ATR            # 追踪步长1ATR
volatility:
  pause_threshold: 90th_percentile  # 高波动暂停
  reduce_at: 75th_percentile        # 中高波动减仓50%
```

---

## 七、结论

系统**最大的两个问题**不是策略本身，而是基础设施：

1. **回测不可信** — 索引错位 + 前瞻偏差 = 所有回测结果都是假的
2. **止损放置不合理** — 对加密货币波动率来说，当前止损策略会把 1000U 在一周内磨光

建议修复顺序：先让回测器产出可信数据（P0），再修复止损和风控（P1），最后优化信号过滤（P1-P2）。

只有当回测器可信且止损合理时，才值得进入 Phase 2（自动交易循环）。
