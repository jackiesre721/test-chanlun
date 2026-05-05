import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  Input,
  Select,
  ListBox,
  Button,
  Chip,
  Disclosure,
  DisclosureTrigger,
  DisclosureContent,
  Checkbox,
} from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { useBacktestOverlayStore } from "@/stores/backtest-overlay-store";
import { postBacktestQuick } from "@/lib/api";
import type {
  BacktestClosedTrade,
  BacktestKindStat,
  BacktestResult,
  BacktestExecTrade,
} from "@/types/analysis";

const STRATEGIES = [
  { value: "long_only_flip", label: "long_only_flip（仅多）" },
  { value: "long_short_flip", label: "long_short_flip（多空）" },
];

const PREVIEW_ROWS = 10;

function localInputToMs(s: string): number | undefined {
  if (!s?.trim()) return undefined;
  const n = new Date(s).getTime();
  return Number.isFinite(n) ? n : undefined;
}

function fmtPxOpt(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(Number(n))) return "—";
  return Number(n).toFixed(2);
}

function KindStatsTable({ stats }: { stats: Record<string, BacktestKindStat> }) {
  const rows = Object.entries(stats).sort((a, b) => b[1].count - a[1].count);
  if (!rows.length) return null;
  return (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-[10px] border-collapse">
        <thead>
          <tr className="text-text-muted border-b border-border-subtle">
            <th className="text-left py-1 pr-2 font-normal">信号类型</th>
            <th className="text-right py-1 px-1 font-normal">样本</th>
            <th className="text-right py-1 px-1 font-normal">胜率</th>
            <th className="text-right py-1 pl-1 font-normal">平均盈亏</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([kind, s]) => (
            <tr key={kind} className="border-b border-white/[0.04]">
              <td className="py-1 pr-2 font-mono">{kind}</td>
              <td className="text-right py-1 px-1">{s.count}</td>
              <td className="text-right py-1 px-1">{(s.win_rate * 100).toFixed(0)}%</td>
              <td className={`text-right py-1 pl-1 ${s.avg_pnl_usdt >= 0 ? "text-success" : "text-danger"}`}>
                {s.avg_pnl_usdt.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradesTable({ rows, preview }: { rows: BacktestClosedTrade[]; preview: boolean }) {
  const shown = preview ? rows.slice(-PREVIEW_ROWS).reverse() : [...rows].reverse();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[10px] border-collapse">
        <thead>
          <tr className="text-text-muted border-b border-border-subtle">
            <th className="text-left py-1 pr-1 font-normal">出场时间</th>
            <th className="text-center py-1 px-1 font-normal">方向</th>
            <th className="text-right py-1 px-1 font-normal">入→出</th>
            <th className="text-right py-1 px-1 font-normal">盈亏</th>
            <th className="text-right py-1 px-1 font-normal">bars</th>
            <th className="text-left py-1 pl-1 font-normal">信号</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((t, i) => (
            <tr key={`${t.exit_time}-${i}`} className="border-b border-white/[0.04]">
              <td className="py-1 pr-1 whitespace-nowrap">{t.exit_time}</td>
              <td className="text-center py-1 px-1">{t.side}</td>
              <td className="text-right py-1 px-1 whitespace-nowrap">
                {t.entry_price.toFixed(2)}→{t.exit_price.toFixed(2)}
              </td>
              <td className={`text-right py-1 px-1 ${t.pnl_usdt >= 0 ? "text-success" : "text-danger"}`}>
                {t.pnl_usdt.toFixed(2)}
              </td>
              <td className="text-right py-1 px-1">{t.bars_held}</td>
              <td className="py-1 pl-1 font-mono">{t.signal_kind_at_entry}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {preview && rows.length > PREVIEW_ROWS && (
        <div className="text-[10px] text-text-muted mt-1">仅展示最近 {PREVIEW_ROWS} 笔完整回合（从新到旧）</div>
      )}
    </div>
  );
}

function ExecTradesTable({ rows, preview }: { rows: BacktestExecTrade[]; preview: boolean }) {
  const shown = preview ? rows.slice(-PREVIEW_ROWS).reverse() : [...rows].reverse();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[10px] border-collapse">
        <thead>
          <tr className="text-text-muted border-b border-border-subtle">
            <th className="text-left py-1 pr-1 font-normal">时间</th>
            <th className="text-center py-1 px-1 font-normal">方向</th>
            <th className="text-right py-1 px-1 font-normal">价</th>
            <th className="text-right py-1 px-1 font-normal">预估SL</th>
            <th className="text-right py-1 px-1 font-normal">TP1</th>
            <th className="text-left py-1 pl-1 font-normal">原因</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((t, i) => (
            <tr key={`${t.time}-${t.bar_idx}-${i}`} className="border-b border-white/[0.04]">
              <td className="py-1 pr-1 whitespace-nowrap max-w-[120px] truncate" title={t.time}>
                {t.time}
              </td>
              <td className="text-center py-1 px-1">{t.action}</td>
              <td className="text-right py-1 px-1">{t.price.toFixed(2)}</td>
              <td className="text-right py-1 px-1 text-warning">{fmtPxOpt(t.stop_loss)}</td>
              <td className="text-right py-1 px-1 text-success">{fmtPxOpt(t.take_profit_1)}</td>
              <td className="py-1 pl-1 font-mono text-[9px] max-w-[72px] truncate" title={t.exit_reason}>
                {t.exit_reason ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {preview && rows.length > PREVIEW_ROWS && (
        <div className="text-[10px] text-text-muted mt-1">仅展示最近 {PREVIEW_ROWS} 笔开/平动作</div>
      )}
    </div>
  );
}

export function BacktestCard() {
  const { symbol, interval } = useSettingsStore();
  const [btSymbol, setBtSymbol] = useState(symbol);
  const [btInterval, setBtInterval] = useState(interval);
  const [strategy, setStrategy] = useState("long_only_flip");
  const [feeBps, setFeeBps] = useState("10");
  const [equity, setEquity] = useState("10000");
  const [leverage, setLeverage] = useState("1");
  const [tradeAmount, setTradeAmount] = useState("");
  const [btStart, setBtStart] = useState("");
  const [btEnd, setBtEnd] = useState("");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [tradesExpanded, setTradesExpanded] = useState(false);
  const [execExpanded, setExecExpanded] = useState(false);

  const setFromRun = useBacktestOverlayStore((s) => s.setFromRun);
  const overlayShow = useBacktestOverlayStore((s) => s.showOverlay);
  const setShowOverlay = useBacktestOverlayStore((s) => s.setShowOverlay);
  const overlayLogLen = useBacktestOverlayStore((s) => s.tradeLog.length);

  useEffect(() => {
    setBtSymbol(symbol);
  }, [symbol]);

  useEffect(() => {
    setBtInterval(interval);
  }, [interval]);

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const ta = tradeAmount.trim() ? Number(tradeAmount) : undefined;
      const lev = Math.max(1, Math.floor(Number(leverage) || 1));
      const r = await postBacktestQuick({
        symbol: btSymbol || symbol,
        interval: btInterval || interval,
        strategy,
        fee_bps: Number(feeBps),
        initial_equity: Number(equity),
        leverage: lev,
        trade_amount_usdt: ta != null && ta > 0 ? ta : undefined,
        start_time_ms: localInputToMs(btStart),
        end_time_ms: localInputToMs(btEnd),
      });
      setResult(r);
      setTradesExpanded(false);
      setExecExpanded(false);
      setFromRun(
        (btSymbol || symbol).trim().toUpperCase(),
        String(btInterval || interval),
        r.trade_log ?? [],
      );
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const closed = result?.closed_trades ?? [];
  const exec = result?.trade_log ?? [];
  const stats = result?.stats_by_signal_kind ?? {};
  const chartAligned =
    (btSymbol || symbol).trim().toUpperCase() === symbol.trim().toUpperCase() &&
    String(btInterval || interval) === String(interval);

  return (
    <Disclosure>
      <Card className="card-glow bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div
            className="section-label cursor-pointer hover:text-accent transition-colors"
            style={{ padding: "10px 12px 8px" }}
          >
            演示回测
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-2">
            <p className="text-[11px] text-text-muted leading-relaxed">
              与后端 <code className="text-[10px]">/backtest/quick</code> 对齐：支持时间段、杠杆、固定保证金、信号止损/强平；
              回合统计与 CHANGELOG 一致。<b>仅供假设检验。</b>
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Input
                aria-label="演示回测品种"
                placeholder="品种"
                value={btSymbol}
                onChange={(e) => setBtSymbol(e.target.value)}
                className="text-sm"
              />
              <Input
                aria-label="演示回测周期码"
                placeholder="周期码"
                value={btInterval}
                onChange={(e) => setBtInterval(e.target.value)}
                className="text-sm"
              />
            <div className="col-span-2 space-y-1">
              <span className="text-[10px] text-text-muted">开始（可选，本地时间）</span>
              <Input
                aria-label="回测开始（本地）"
                type="datetime-local"
                className="text-sm"
                value={btStart}
                onChange={(e) => setBtStart(e.target.value)}
              />
            </div>
            <div className="col-span-2 space-y-1">
              <span className="text-[10px] text-text-muted">结束（可选）</span>
              <Input
                aria-label="回测结束（本地）"
                type="datetime-local"
                className="text-sm"
                value={btEnd}
                onChange={(e) => setBtEnd(e.target.value)}
              />
            </div>
              <Select
                aria-label="演示回测策略"
                selectedKey={strategy}
                onSelectionChange={(key) => key && setStrategy(key as string)}
              >
                <Select.Trigger>
                  <Select.Value />
                </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {STRATEGIES.map((s) => (
                      <ListBox.Item key={s.value} id={s.value}>
                        {s.label}
                      </ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
              </Select>
              <Input
                aria-label="演示回测手续费（基点）"
                placeholder="手续费 bps"
                type="number"
                value={feeBps}
                onChange={(e) => setFeeBps(e.target.value)}
                className="text-sm"
              />
              <Input
                aria-label="杠杆"
                placeholder="杠杆 1–100"
                type="number"
                value={leverage}
                onChange={(e) => setLeverage(e.target.value)}
                className="text-sm"
              />
              <Input
                aria-label="每笔保证金 USDT"
                placeholder="每笔保证金（空=全仓）"
                type="number"
                value={tradeAmount}
                onChange={(e) => setTradeAmount(e.target.value)}
                className="text-sm"
              />
              <Input
                aria-label="演示回测初始权益"
                placeholder="初始权益"
                type="number"
                value={equity}
                onChange={(e) => setEquity(e.target.value)}
                className="text-sm col-span-2"
              />
            </div>
            <p className="text-[10px] text-text-muted">
              不设开始时间时，服务端按配置拉取最近一段 K 线；时间段与 toolbar 品种/周期相互独立，叠加主图时需与当前主图一致。
            </p>
            <Button size="sm" variant="primary" className="w-full" onPress={run} isDisabled={loading}>
              {loading ? "运行中…" : "运行演示回测"}
            </Button>
            {error && <div className="text-xs text-negative">{error}</div>}

            {exec.length > 0 && (
              <div className="flex flex-col gap-1 pt-1 border-t border-border-subtle">
                <Checkbox
                  isSelected={overlayShow && overlayLogLen > 0}
                  isDisabled={overlayLogLen === 0}
                  onChange={() => setShowOverlay(!overlayShow)}
                >
                  <span className="text-[11px]">主图叠加回测成交（▲买 / ▼卖）</span>
                </Checkbox>
                {!chartAligned && (
                  <span className="text-[10px] text-warning leading-snug">
                    当前主图 {symbol}/{interval} 与上方回测参数不一致时不会绘制叠加。
                  </span>
                )}
              </div>
            )}

            {result && (
              <div className="space-y-2 mt-2">
                <div className="flex flex-wrap gap-1.5">
                  <Chip size="sm" variant="soft" title="相对初始权益的总收益率">
                    收益 {(result.total_return_pct >= 0 ? "+" : "") + result.total_return_pct.toFixed(2)}%
                  </Chip>
                  <Chip size="sm" variant="soft" color="danger" title="样本期内权益峰值回撤比例">
                    回撤 {result.max_drawdown_pct.toFixed(2)}%
                  </Chip>
                  <Chip size="sm" variant="soft" title="基于相邻成交后权益波动的朴素夏普近似">
                    Sharpe {result.sharpe_ratio != null ? result.sharpe_ratio.toFixed(2) : "—"}
                  </Chip>
                  <Chip size="sm" variant="soft" title="撮合动作次数（开/平）">
                    动作 {result.trade_count}
                  </Chip>
                  <Chip size="sm" variant="soft" title="完整开仓→空仓回合数">
                    回合 {result.closed_trade_count ?? closed.length}
                  </Chip>
                  <Chip size="sm" variant="soft" title="回合盈亏为正的比例">
                    胜率 {result.win_rate_pct != null ? `${result.win_rate_pct.toFixed(1)}%` : "—"}
                  </Chip>
                  {result.stop_loss_hits != null && result.stop_loss_hits > 0 && (
                    <Chip size="sm" variant="soft" color="warning" title="触及信号止损价的次数">
                      止损触发 {result.stop_loss_hits}
                    </Chip>
                  )}
                </div>

                <Disclosure>
                  <DisclosureTrigger>
                    <div className="text-[11px] font-semibold text-accent cursor-pointer hover:underline">
                      次级指标 · 按信号分类
                    </div>
                  </DisclosureTrigger>
                  <DisclosureContent>
                    <div className="text-[11px] text-text-muted space-y-1 pt-1 border-t border-border-subtle mt-1">
                      <div>K 线样本：{result.bars_used ?? "—"}</div>
                      <div>
                        盈亏比（毛利/毛亏）：{" "}
                        {result.profit_factor != null ? result.profit_factor.toFixed(2) : "—"}
                      </div>
                      <div>
                        每笔期望（USDT）：{" "}
                        {result.expectancy_per_trade_usdt != null
                          ? result.expectancy_per_trade_usdt.toFixed(4)
                          : "—"}
                      </div>
                      <div>最大连亏（回合）：{result.max_consecutive_losses ?? "—"}</div>
                      <div>
                        均盈 / 均亏：{" "}
                        {result.avg_win_usdt != null ? result.avg_win_usdt.toFixed(2) : "—"} /{" "}
                        {result.avg_loss_usdt != null ? result.avg_loss_usdt.toFixed(2) : "—"}
                      </div>
                      <KindStatsTable stats={stats} />
                    </div>
                  </DisclosureContent>
                </Disclosure>

                {exec.length > 0 && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold text-text-primary">成交明细（SL/TP1）</span>
                      {exec.length > PREVIEW_ROWS && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-[10px] min-h-7 h-7 px-2"
                          onPress={() => setExecExpanded((v) => !v)}
                        >
                          {execExpanded ? "只看最近10笔" : `展开全部 (${exec.length})`}
                        </Button>
                      )}
                    </div>
                    <ExecTradesTable rows={exec} preview={!execExpanded && exec.length > PREVIEW_ROWS} />
                  </div>
                )}

                {closed.length > 0 && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold text-text-primary">回合明细</span>
                      {closed.length > PREVIEW_ROWS && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-[10px] min-h-7 h-7 px-2"
                          onPress={() => setTradesExpanded((v) => !v)}
                        >
                          {tradesExpanded ? "只看最近10笔" : `展开全部 (${closed.length})`}
                        </Button>
                      )}
                    </div>
                    <TradesTable rows={closed} preview={!tradesExpanded && closed.length > PREVIEW_ROWS} />
                  </div>
                )}

                {result.disclaimer && (
                  <p className="text-[10px] text-text-muted opacity-70 leading-snug">{result.disclaimer}</p>
                )}
              </div>
            )}
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
