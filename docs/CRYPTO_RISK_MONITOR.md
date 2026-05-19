# 加密货币宏观风险监控系统 — 架构文档

> 版本：v2.0 · 日期：2026-05-09
> 技术栈：OpenClaw + 飞书 + 缠论信号系统
> 状态：**已部署运行**

---

## 1. 系统目标

实时监控全球 6 大类 30+ 加密货币风险信息源，AI 交叉验证后输出风险评级（RED/YELLOW/GREEN），**仅在风险等级变化时**推送飞书卡片。用户根据卡片自行决定是否交易。

**核心原则：全自动信息采集 + 风险研判 + 飞书推送，不干预交易逻辑。**

---

## 2. 整体架构

```
┌───────────────────────────────────────────────────────────────────┐
│                     6 大类 30+ 信息源                              │
│                                                                   │
│  ① 政策监管          ② 加密行业          ③ 宏观经济               │
│  Trump/白宫          交易所公告          美联储/CPI/非农           │
│  SEC/CFTC            链上异动/鲸鱼       美债/VIX/DXY             │
│  各国监管            安全事件/黑客       GDP/利率决议              │
│                                                                   │
│  ④ 地缘政治          ⑤ 市场数据          ⑥ 社区舆情               │
│  战争/冲突           恐惧贪婪指数        X KOL 分析师             │
│  制裁/贸易战         资金费率/清算        Reddit 热帖              │
│  能源危机            BTC Dominance       中文圈快讯                │
└───────┬──────────────────┬──────────────────┬──────────────────────┘
        │ Webhook          │ Cron/API         │ RSS
        │ (<1min)          │ (15min)          │ (1-5min)
        ▼                  ▼                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                       OpenClaw Gateway                             │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Webhook 桥接（FastAPI :18800）                               │ │
│  │  /hooks/crypto-twitter   /hooks/crypto-news                  │ │
│  │  /hooks/crypto-onchain   /hooks/crypto-macro                 │ │
│  │  → openclaw system event 注入主会话                           │ │
│  └────────────────────────────┬─────────────────────────────────┘ │
│                               │                                    │
│  ┌────────────────────────────┼────────────────────────────────┐ │
│  │  Cron 定时扫描（兜底，每 15 分钟）                           │ │
│  │  扫描 6 类信息源 + 市场数据 API + 经济日历                   │ │
│  └────────────────────────────┼────────────────────────────────┘ │
│                               │                                    │
│  ┌────────────────────────────┼────────────────────────────────┐ │
│  │  经济日历 Cron（每日 7/13/19 点）                            │ │
│  └────────────────────────────┼────────────────────────────────┘ │
│                               │                                    │
│                               ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  crypto-risk-monitor Skill                                   │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐   │ │
│  │  │ 6源采集  │→ │ AI 交叉验证  │→ │ 状态文件 + 飞书卡片  │   │ │
│  │  │ 并行汇总 │  │ 多源评级融合 │  │ 仅等级变化时推送     │   │ │
│  │  └──────────┘  └──────────────┘  └──────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  飞书群风险卡片   │
                    │  RED / YELLOW /   │
                    │  GREEN            │
                    └──────────────────┘
```

---

## 3. 双层触发机制

| 层级 | 触发方式 | 延迟 | 用途 |
|------|----------|------|------|
| L1 | Webhook 桥接（事件驱动） | < 1 分钟 | X 发帖、新闻发布、链上异动、宏观数据 — 立即触发 |
| L2 | OpenClaw Cron（每 15 分钟） | ≤ 15 分钟 | 兜底全景扫描，防止漏掉 L1 未捕获的事件 |
| 辅助 | 经济日历 Cron（每日 3 次） | 定时 | CPI/非农/FOMC 发布日额外关注 |

系统全自动运行，风险变化时主动推送飞书卡片，无需人工干预。

---

## 4. 已部署组件

### 4.1 OpenClaw Skill：`crypto-risk-monitor`

**位置**：`~/.openclaw/skills/crypto-risk-monitor/SKILL.md`

**功能**：
1. **信息采集** — 从 6 大类信息源收集最新动态
2. **AI 风险研判** — 交叉验证后输出风险评级
3. **状态持久化** — 写入 `~/.openclaw/workspace/crypto-risk-state.json`
4. **飞书推送** — 仅在风险等级变化时推送对应颜色的飞书卡片

**风险等级定义**：

| 等级 | 颜色 | 判断标准 | 动作 |
|------|------|----------|------|
| GREEN | 🟢 | 无重大负面消息，市场正常 | 无操作（从 RED/YELLOW 降级时推送绿色解除卡片） |
| YELLOW | 🟡 | 存在潜在风险（政策讨论、市场波动加大） | 推送黄色预警卡片 |
| RED | 🔴 | 黑天鹅事件（战争、重大制裁、交易所暴雷、极端政策） | 推送红色警报卡片 |

**推送策略（push-on-change）**：
- 读取状态文件获取上次风险等级
- 新等级与旧等级对比
- **仅在等级变化时**推送飞书卡片
- 降级（RED→GREEN）也推送解除警报卡片

### 4.2 Cron 任务

| 任务名 | 调度 | 说明 |
|--------|------|------|
| `crypto-risk-scan` | `*/15 * * * *` (Asia/Shanghai) | 每 15 分钟全景扫描 6 类信息源 |
| `crypto-risk-macro` | `0 7,13,19 * * *` (Asia/Shanghai) | 每日 7/13/19 点检查经济日历 |

**管理命令**：
```bash
openclaw cron list              # 查看所有任务
openclaw cron run crypto-risk-scan   # 手动触发扫描
```

### 4.3 Webhook 桥接服务

**位置**：`scripts/risk_webhook_bridge.py`
**端口**：18800
**launchd 服务**：`com.chanlan.risk-webhook`（KeepAlive + RunAtLoad）

| 端点 | 触发源 | 数据格式 |
|------|--------|----------|
| `POST /hooks/crypto-twitter` | X/Twitter 事件（N8N/IFTTT 转发） | `{ "author": "...", "text": "...", "url": "..." }` |
| `POST /hooks/crypto-news` | 新闻 RSS 聚合 | `{ "title": "...", "source": "...", "summary": "..." }` |
| `POST /hooks/crypto-onchain` | 链上监控 | `{ "type": "whale\|hack\|rug", "chain": "...", "detail": "..." }` |
| `POST /hooks/crypto-macro` | 宏观经济数据 | `{ "indicator": "CPI\|NFP\|FOMC", "value": "...", "expected": "..." }` |

**特性**：60 秒去重、`openclaw system event` 注入主会话、launchd 自动重启。

**测试**：
```bash
curl http://localhost:18800/health    # 健康检查
curl -X POST http://localhost:18800/hooks/crypto-twitter \
  -H "Content-Type: application/json" \
  -d '{"author":"test","text":"test","url":"test"}'
```

### 4.4 状态文件

**位置**：`~/.openclaw/workspace/crypto-risk-state.json`

Skill 每次扫描后更新此文件，记录当前风险等级、分类评级和关键事件。

### 4.5 OpenClaw 飞书通道

**配置**：`~/.openclaw/openclaw.json` → `channels.feishu`
**凭证**：复用 `scripts/.env` 中的飞书应用（`cli_a97022b1ebb9dcdd`）
**目标群**：`oc_37013a6979c00bd481d8955496578783`

---

## 5. 飞书卡片

### RED 卡片（黑天鹅风险警报）

header template: `red`，包含风险摘要、6 类分类评级、关键事件、信息来源、详细分析。

### YELLOW 卡片（宏观风险预警）

header template: `orange`，同 RED 结构。

### GREEN 卡片（风险解除）

header template: `green`，仅在从 RED/YELLOW 降级时推送。

---

## 6. 信息源策略（全景覆盖）

### 6.1 政策与监管（权重：★★★★★）

| 信息源 | 账号 | 关注内容 | 接入方式 |
|--------|------|----------|----------|
| **特朗普/白宫** | @realDonaldTrump, @WhiteHouse | 加密货币政策、关税、经济刺激、行政令 | X Webhook |
| **SEC** | @SECGov | 加密货币监管行动、ETF 审批/拒绝、执法 | X Webhook + RSS |
| **CFTC** | @CFTC | 期货/衍生品监管 | X Webhook |
| **美联储** | @federalreserve | 利率决议、鲍威尔讲话、FOMC 声明 | RSS + Cron |
| **美国财政部** | @USTreasury | 制裁名单更新、加密税收政策 | X Webhook |
| **各国监管** | — | 中国禁令、欧盟 MiCA、日本 FSA、韩国监管 | 新闻 RSS 聚合 |

### 6.2 加密行业动态（权重：★★★★☆）

| 信息源 | 账号 | 关注内容 | 接入方式 |
|--------|------|----------|----------|
| **Binance** | @binance, @BinanceAlerts | 交易所公告、维护、上/下币 | X Webhook |
| **Coinbase** | @CoinbaseAssets | 上币公告、合规进展 | X Webhook |
| **OKX / Bybit** | @okx, @Bybit_Official | 交易所公告 | X Webhook |
| **DeFi 协议** | @Uniswap, @AaveAave, @LidoFinance | 协议升级、安全事件 | X Webhook |
| **链上监控** | Whale Alert API / Arkham | 大额转账、鲸鱼异动 | API → Webhook |
| **安全事件** | @CertiKAlert, @peckshield | 智能合约漏洞、黑客攻击、Rug Pull | X Webhook |
| **稳定币** | @circle, @Tether_to | 脱锚、储备审计 | X Webhook |

### 6.3 宏观经济指标（权重：★★★★☆）

| 指标 | 影响 | 接入方式 |
|------|------|----------|
| 美联储利率决议 | 直接影响风险资产定价 | Cron（FOMC 日历） |
| CPI | 高于预期→避险；低于预期→利好 | Cron（每月发布日） |
| 非农就业数据 | 强于预期→加息预期↑→加密承压 | Cron（每月第一个周五） |
| GDP 增长率 | 衰退→避险；过热→加息 | Cron（季度发布） |
| 美债收益率 | 收益率飙升→风险资产承压 | API 定时检查 |
| VIX 恐慌指数 | VIX > 30 = 市场恐慌 | API 定时检查 |
| DXY 美元指数 | 美元走强→加密承压 | API 定时检查 |

### 6.4 地缘政治（权重：★★★★★）

| 信息源 | 影响 | 接入方式 |
|--------|------|----------|
| 俄乌冲突 | 能源价格→通胀→加密波动 | 新闻 RSS |
| 中东局势 | 地缘风险→避险情绪 | 新闻 RSS |
| 美中关系 | 全球市场连锁反应 | X Webhook + RSS |
| 制裁事件 | 影响加密合规和流动性 | RSS |
| 能源危机 | 通胀→加息预期→加密承压 | RSS + API |

新闻聚合：Reuters, AP News, Bloomberg, FT, CNN Breaking News

### 6.5 市场数据与情绪（权重：★★★☆☆）

| 指标 | 来源 | 阈值 |
|------|------|------|
| 恐惧贪婪指数 | alternative.me | < 15 = RED；< 25 = YELLOW |
| BTC 资金费率 | Binance API | > 0.1% = YELLOW；< -0.1% = YELLOW |
| 24h 清算量 | Coinglass API | > 5 亿 = YELLOW；> 10 亿 = RED |
| BTC Dominance | CoinGecko API | 快速飙升/下跌 = 异常 |
| 总市值变化 | CoinGecko API | 24h 跌 > 10% = 异常 |
| 交易所净流入 | Glassnode / CryptoQuant | 大量流入 = 抛压信号 |

### 6.6 社区与舆情（权重：★★★☆☆）

| 信息源 | 内容 | 接入方式 |
|--------|------|----------|
| X/Twitter KOL | @CryptoCapo_, @CryptoDonAlt 等分析师 | X Webhook |
| Reddit | r/cryptocurrency, r/bitcoin | RSS |
| 中文圈 | 金色财经、BlockBeats 快讯 | 新闻 RSS |

---

## 7. AI 交叉验证逻辑

```
信息采集（6 类并行）
    │
    ├─→ 政策监管：是否有新政策/监管行动？
    ├─→ 加密行业：是否有交易所/链上/安全异常？
    ├─→ 宏观经济：是否有重大数据发布？
    ├─→ 地缘政治：是否有冲突升级？
    ├─→ 市场数据：指标是否异常？
    └─→ 社区舆情：是否有恐慌/过热信号？
    │
    ▼
交叉验证评分
    ├─ 单源 + 影响重大 → RED（如：Trump 宣布加密禁令）
    ├─ 单源 + 影响中等 → YELLOW（如：SEC 起诉某项目）
    ├─ 2+ 类同时 YELLOW → 自动升级 RED
    ├─ 3+ 类同时异常 → 自动升级 RED
    ├─ 链上安全事件 → 直接 RED
    └─ 无异常 → GREEN
    │
    ▼
对比上次等级 → 仅变化时推送飞书卡片 + 更新状态文件
```

---

## 8. 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `~/.openclaw/skills/crypto-risk-monitor/SKILL.md` | 新建 | OpenClaw Skill 定义 |
| `~/.openclaw/workspace/crypto-risk-state.json` | 运行时 | 风险状态持久化 |
| `~/.openclaw/openclaw.json` | 修改 | 飞书通道凭证 |
| `~/.openclaw/extensions/feishu/node_modules/` | 修复 | 飞书插件依赖 |
| `scripts/risk_webhook_bridge.py` | 新建 | Webhook 桥接服务 |
| `~/Library/LaunchAgents/com.chanlan.risk-webhook.plist` | 新建 | 桥接服务 launchd 配置 |
| `.cache/risk-webhook.log` / `.cache/risk-webhook.err` | 运行时 | 桥接服务日志 |
| `docs/CRYPTO_RISK_MONITOR.md` | 本文档 | 架构文档 |

---

## 9. 管理命令

```bash
# 查看系统状态
openclaw status

# 查看 Cron 任务
openclaw cron list

# 手动触发风险扫描
openclaw cron run crypto-risk-scan

# 查看当前风险状态
cat ~/.openclaw/workspace/crypto-risk-state.json

# 查看桥接服务日志
tail -f .cache/risk-webhook.log

# 重启桥接服务
launchctl unload ~/Library/LaunchAgents/com.chanlan.risk-webhook.plist
launchctl load ~/Library/LaunchAgents/com.chanlan.risk-webhook.plist

# 测试飞书通道
openclaw message send --channel feishu --account main \
  --target "oc_37013a6979c00bd481d8955496578783" \
  --message "测试消息"

# 测试 Webhook 端点
curl -s http://localhost:18800/health
curl -X POST http://localhost:18800/hooks/crypto-twitter \
  -H "Content-Type: application/json" \
  -d '{"author":"test","text":"test crypto event","url":"test"}'
```

---

## 10. 待完成

- [ ] 调优 SKILL.md Prompt（减少误报/漏报）
- [ ] 按需接入 Webhook 外部触发（X/Twitter、RSS、链上监控、经济日历 → `/hooks/*`）
