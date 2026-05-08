# 每日信号推送 — 部署文档

## 架构

```
launchd (常驻)          crontab (每天07:00)
    │                        │
    ▼                        ▼
 后端 :8000 ──────→ scripts/daily_signal.py ──→ 飞书群卡片
 (缠论引擎)          (拉信号+算仓位+发卡片)
                              │
                              ▼
                    .cache/chanlan/trade_journal.sqlite
                         (交易日志持久化)
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `scripts/daily_signal.py` | 信号推送 + 交易日志脚本 |
| `scripts/.env` | 配置文件（飞书凭证、交易参数） |
| `scripts/.env.example` | 配置模板 |
| `scripts/cron.log` | cron 执行日志 |
| `.cache/chanlan/trade_journal.sqlite` | 交易日志数据库 |
| `.cache/backend.log` / `.cache/backend.err` | 后端服务日志 |
| `~/Library/LaunchAgents/com.chanlan.backend.plist` | 后端常驻服务 |

## 配置

编辑 `scripts/.env`：

```bash
BACKEND_URL=http://localhost:8000

# 飞书应用凭证
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_CHAT_ID=oc_xxx

# 交易参数
SYMBOL=SOLUSDT        # 扫描品种
INTERVAL=60           # K线周期（分钟）
EQUITY=200            # 本金（USDT）
LEVERAGE=5            # 杠杆倍数
RISK_FRAC=0.02        # 单笔风险比例（2%）
MAINT_RATE=0.004      # 维持保证金率

# 交易时段
TRADING_START=7       # 开始（24h）
TRADING_END=19        # 结束（24h）
```

## 命令用法

### push — 推送今日信号（默认）

```bash
python3 scripts/daily_signal.py              # 正常执行（检查交易时段）
python3 scripts/daily_signal.py push          # 同上
python3 scripts/daily_signal.py push --force  # 忽略时段限制
python3 scripts/daily_signal.py push --dry-run  # 只打印不发送
```

推送时自动保存到交易日志，状态为 `pending`。

### log — 查看交易日志

```bash
python3 scripts/daily_signal.py log           # 最近 20 条
python3 scripts/daily_signal.py log --last 5  # 最近 5 条
```

### update — 更新交易结果

```bash
# 标记已入场（填写实际成交价）
python3 scripts/daily_signal.py update 1 --status filled --entry 87.6

# 标记止盈/止损（填写实际出场价和盈亏）
python3 scripts/daily_signal.py update 1 --status tp_hit --exit 92.2 --pnl 4.0 --notes "TP1止盈"

# 标记止损
python3 scripts/daily_signal.py update 1 --status sl_hit --exit 82.9 --pnl -4.0

# 取消
python3 scripts/daily_signal.py update 1 --status cancelled --notes "没到价位"
```

状态说明：

| 状态 | 含义 |
|------|------|
| `pending` | 等待入场（推送时自动创建） |
| `filled` | 已入场 |
| `closed` | 手动平仓 |
| `sl_hit` | 止损成交 |
| `tp_hit` | 止盈成交 |
| `cancelled` | 已取消 |

### review — 推送复盘报告到飞书

```bash
python3 scripts/daily_signal.py review           # 发送复盘卡片
python3 scripts/daily_signal.py review --dry-run  # 只打印不发送
```

复盘卡片包含：总交易数、已平仓、胜率、累计盈亏、初始本金、当前净值、收益率、最近交易明细。

## 自动执行（cron）

已配置 crontab，每天 07:00 自动推送：

```
0 7 * * * /usr/bin/python3 /Users/richie/test-chanlun/scripts/daily_signal.py >> /Users/richie/test-chanlun/scripts/cron.log 2>&1
```

查看/修改：

```bash
crontab -l                # 查看
crontab -e                # 编辑
```

## 后端常驻服务（launchd）

后端通过 macOS launchd 管理为系统服务：

| 特性 | 配置 |
|------|------|
| 开机自启 | `RunAtLoad = true` |
| 崩溃自重启 | `KeepAlive = true` |
| 标准输出 | `.cache/backend.log` |
| 错误输出 | `.cache/backend.err` |

管理命令：

```bash
# 查看状态
launchctl list | grep chanlan

# 启动
launchctl load ~/Library/LaunchAgents/com.chanlan.backend.plist

# 停止
launchctl unload ~/Library/LaunchAgents/com.chanlan.backend.plist

# 重启
launchctl unload ~/Library/LaunchAgents/com.chanlan.backend.plist
launchctl load ~/Library/LaunchAgents/com.chanlan.backend.plist
```

## 防休眠（MacBook）

保持电脑不休眠，合盖也继续运行：

```bash
sudo pmset -a sleep 0           # 永不休眠
sudo pmset -a disablesleep 1    # 合盖不休眠
sudo pmset -a displaysleep 10   # 屏幕10分钟关（省电）
sudo pmset -a disksleep 0       # 硬盘不休眠
```

确认生效：

```bash
pmset -g | grep -E "sleep|displaysleep"
```

建议一直插着电源。

## 每日操作流程

1. **07:00** — cron 自动推送信号卡片到飞书
2. **看飞书** — 确认今日信号（品种、方向、入场价、止损、止盈）
3. **挂单** — 在 Binance 挂限价单 + OCO 止损止盈
4. **更新日志** — 操作后更新交易记录：
   ```bash
   python3 scripts/daily_signal.py update <id> --status filled --entry <实际价>
   ```
5. **收盘后** — 平仓后更新结果：
   ```bash
   python3 scripts/daily_signal.py update <id> --status tp_hit --exit <实际价> --pnl <盈亏>
   ```
6. **复盘** — 推送复盘报告：
   ```bash
   python3 scripts/daily_signal.py review
   ```

## 交易纪律

- 每天最多 1 单
- 只在 07:00 - 19:00 交易
- 杠杆固定 5x
- 单笔风险固定 2%
- 限价单入场，OCO 止损止盈自动成交
