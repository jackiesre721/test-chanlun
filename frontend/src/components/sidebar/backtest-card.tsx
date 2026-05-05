import { useState } from "react";
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
} from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { postBacktestQuick } from "@/lib/api";
import type { BacktestClosedTrade, BacktestKindStat, BacktestResult } from "@/types/analysis";

const STRATEGIES = [
  { value: "long_only_flip", label: "long_only_flip（仅多）" },
  { value: "long_short_flip", label: "long_short_flip（多空）" },
];

const PREVIEW_ROWS = 10;

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

export function BacktestCard() {
  const { symbol, interval } = useSettingsStore();
  const [btSymbol, setBtSymbol] = useState(symbol);
  const [btInterval, setBtInterval] = useState(interval);
  const [maxBars, setMaxBars] = useState("6000");
  const [strategy, setStrategy] = useState("long_only_flip");
  const [feeBps, setFeeBps] = useState("10");
  const [equity, setEquity] = useState("10000");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [tradesExpanded, setTradesExpanded] = useState(false);

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await postBacktestQuick({
        symbol: btSymbol || symbol,
        interval: btInterval || interval,
        max_bars: Number(maxBars),
        strategy,
        fee_bps: Number(feeBps),
        initial_equity: Number(equity),
      });
      setResult(r);
      setTradesExpanded(false);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const closed = result?.closed_trades ?? [];
  const stats = result?.stats_by_signal_kind ?? {};

  return (
    <Disclosure defaultOpen>
      <Card className="card-glow bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div className="section-label cursor-pointer hover:text-accent transition-colors" style={{ padding: "10px 12px 8px" }}>
            演示回测
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-2">
            <p className="text-[11px] text-text-muted leading-relaxed">
              简化信号撮合 + 手续费；回合盈亏按<strong>开仓前权益 → 平仓后权益</strong>估算。
              <b>仅供假设检验。</b>
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Input aria-label="演示回测品种" placeholder="品种" value={btSymbol} onChange={(e) => setBtSymbol(e.target.value)} className="text-sm" />
              <Input aria-label="演示回测周期码" placeholder="周期码" value={btInterval} onChange={(e) => setBtInterval(e.target.value)} className="text-sm" />
              <Input aria-label="演示回测 K 线根数" placeholder="bars" type="number" value={maxBars} onChange={(e) => setMaxBars(e.target.value)} className="text-sm" />
              <Select aria-label="演示回测策略" selectedKey={strategy} onSelectionChange={(key) => key && setStrategy(key as string)}>
                <Select.Trigger>
                  <Select.Value placeholder="策略" />
                </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {STRATEGIES.map((s) => (
                      <ListBox.Item key={s.value} id={s.value}>{s.label}</ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
              </Select>
              <Input aria-label="演示回测手续费（基点）" placeholder="手续费 bps" type="number" value={feeBps} onChange={(e) => setFeeBps(e.target.value)} className="text-sm" />
              <Input aria-label="演示回测初始权益" placeholder="初始权益" type="number" value={equity} onChange={(e) => setEquity(e.target.value)} className="text-sm" />
            </div>
            <Button size="sm" color="primary" className="w-full" onPress={run} isDisabled={loading}>
              {loading ? "运行中…" : "运行演示回测"}
            </Button>
            {error && <div className="text-xs text-negative">{error}</div>}

            {result && (
              <div className="space-y-2 mt-2">
                <div className="flex flex-wrap gap-1.5">
                  <Chip size="sm" variant="flat" title="相对初始权益的总收益率">
                    收益 {(result.total_return_pct >= 0 ? "+" : "") + result.total_return_pct.toFixed(2)}%
                  </Chip>
                  <Chip size="sm" variant="flat" color="danger" title="样本期内权益峰值回撤比例">
                    回撤 {result.max_drawdown_pct.toFixed(2)}%
                  </Chip>
                  <Chip size="sm" variant="flat" title="基于相邻成交后权益波动的朴素夏普近似">
                    Sharpe {result.sharpe_ratio != null ? result.sharpe_ratio.toFixed(2) : "—"}
                  </Chip>
                  <Chip size="sm" variant="flat" title="撮合动作次数（开/平单次信号）">
                    动作 {result.trade_count}
                  </Chip>
                  <Chip size="sm" variant="flat" title="完整开仓→空仓回合数">
                    回合 {result.closed_trade_count ?? closed.length}
                  </Chip>
                  <Chip size="sm" variant="flat" title="回合盈亏为正的比例">
                    胜率{" "}
                    {result.win_rate_pct != null ? `${result.win_rate_pct.toFixed(1)}%` : "—"}
                  </Chip>
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

                {closed.length > 0 && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold text-text-primary">回合明细</span>
                      {closed.length > PREVIEW_ROWS && (
                        <Button size="sm" variant="light" className="text-[10px] min-h-7 h-7 px-2" onPress={() => setTradesExpanded((v) => !v)}>
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
