import { useRef, useEffect, useState } from "react";
import * as echarts from "echarts";
import { Card, CardContent, Input, Button } from "@heroui/react";
import { Disclosure, DisclosureTrigger, DisclosureContent } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { postBacktestQuick } from "@/lib/api";
import type { BacktestResult, BacktestRoundTrip, BacktestTrade } from "@/types/analysis";
import { INTERVAL_LABEL } from "@/constants/level-maps";

const FEE_BPS = 10;
const STRATEGY = "long_short_flip";
const TRADE_FRACTION = 0.1;
const MIN_TRADE_AMOUNT = 10;

function formatBarsHeld(bars: number, intervalMinutes: number): string {
  const totalMin = bars * intervalMinutes;
  if (totalMin < 60) return `${totalMin}m`;
  if (totalMin < 1440) {
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    return m > 0 ? `${h}h${m}m` : `${h}h`;
  }
  const d = Math.floor(totalMin / 1440);
  const h = Math.floor((totalMin % 1440) / 60);
  return h > 0 ? `${d}d${h}h` : `${d}d`;
}

const INTERVAL_MINUTES: Record<string, number> = {
  "1": 1, "5": 5, "15": 15, "30": 30, "60": 60,
  "240": 240, "1440": 1440, "10080": 10080, "43200": 43200,
};

function toDatetimeLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function defaultStartTime(): string {
  return toDatetimeLocal(new Date(Date.now() - 30 * 86400000));
}

function defaultEndTime(): string {
  return toDatetimeLocal(new Date());
}

function EquityChart({ trades }: { trades: BacktestTrade[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current, undefined, { renderer: "canvas" });
    chartRef.current = chart;

    const onResize = () => { if (!chart.isDisposed()) chart.resize(); };
    window.addEventListener("resize", onResize);
    const ro = new ResizeObserver(onResize);
    ro.observe(containerRef.current);

    return () => {
      window.removeEventListener("resize", onResize);
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || chart.isDisposed()) return;

    if (!trades.length) {
      chart.clear();
      return;
    }

    const data = trades.map((t, i) => [i, t.equity_after]);
    const labels = trades.map((t) => t.time);

    chart.setOption({
      backgroundColor: "transparent",
      animation: false,
      grid: { left: 50, right: 12, top: 8, bottom: 20 },
      xAxis: { type: "category", data: labels, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: "rgba(255,255,255,.08)" } } },
      yAxis: { type: "value", scale: true, axisLabel: { color: "rgba(209,214,224,.55)", fontSize: 9 }, splitLine: { lineStyle: { color: "rgba(255,255,255,.05)", type: "dashed" } } },
      series: [{
        type: "line", data, step: "middle", symbol: "none",
        lineStyle: { color: "#42a5f5", width: 1.5 },
        areaStyle: { color: "rgba(66,165,245,.08)" },
      }],
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(14,17,24,.94)",
        borderColor: "rgba(255,255,255,.09)",
        textStyle: { color: "#e8eaf0", fontSize: 10 },
        formatter(p: any[]) {
          const pt = p[0];
          if (!pt) return "";
          const t = trades[pt.dataIndex];
          return `${t?.time || ""}<br/>权益: ${pt.value[1]?.toFixed(2)} U`;
        },
      },
    }, { notMerge: true });
  }, [trades]);

  return <div ref={containerRef} className="w-full" style={{ height: 120 }} />;
}

function TradeTable({ trades, tradeLog, intervalMinutes }: { trades: BacktestRoundTrip[]; tradeLog: BacktestTrade[]; intervalMinutes: number }) {
  if (!trades.length) return null;

  const exitReasons = new Map<string, string>();
  for (const t of tradeLog) {
    if (t.action === "SELL" || t.action === "BUY") {
      const key = `${t.bar_idx}-${t.time}`;
      exitReasons.set(key, t.exit_reason);
    }
  }

  return (
    <div className="overflow-y-auto max-h-[240px] scrollbar-thin">
      <table className="w-full text-[11px]">
        <thead className="sticky top-0 bg-bg-card z-10">
          <tr className="text-text-muted border-b border-border-subtle">
            <th className="text-left py-1 px-1 font-medium">#</th>
            <th className="text-left py-1 px-1 font-medium">方向</th>
            <th className="text-left py-1 px-1 font-medium">买入时间</th>
            <th className="text-right py-1 px-1 font-medium">买入价</th>
            <th className="text-left py-1 px-1 font-medium">卖出时间</th>
            <th className="text-right py-1 px-1 font-medium">卖出价</th>
            <th className="text-right py-1 px-1 font-medium">盈亏</th>
            <th className="text-right py-1 px-1 font-medium">持仓</th>
            <th className="text-left py-1 px-1 font-medium">平仓</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
            const reasonKey = `${t.exit_bar_idx}-${t.exit_time}`;
            const reason = exitReasons.get(reasonKey) || "signal";
            const reasonLabel: Record<string, string> = { signal: "信号", stop_loss: "止损", liquidation: "强平" };
            return (
              <tr key={i} className="border-b border-border-subtle/40 hover:bg-white/[0.02]">
                <td className="py-0.5 px-1 text-text-muted">{i + 1}</td>
                <td className="py-0.5 px-1">
                  <span className={t.side === "LONG" ? "text-success" : "text-danger"}>{t.side === "LONG" ? "多" : "空"}</span>
                </td>
                <td className="py-0.5 px-1 text-text-secondary whitespace-nowrap">{t.entry_time}</td>
                <td className="py-0.5 px-1 text-right">{t.entry_price.toFixed(2)}</td>
                <td className="py-0.5 px-1 text-text-secondary whitespace-nowrap">{t.exit_time}</td>
                <td className="py-0.5 px-1 text-right">{t.exit_price.toFixed(2)}</td>
                <td className={`py-0.5 px-1 text-right font-medium ${t.pnl_usdt >= 0 ? "text-success" : "text-danger"}`}>
                  {t.pnl_usdt >= 0 ? "+" : ""}{t.pnl_usdt.toFixed(2)}
                </td>
                <td className="py-0.5 px-1 text-right text-text-muted">{formatBarsHeld(t.bars_held, intervalMinutes)}</td>
                <td className="py-0.5 px-1 text-text-muted">{reasonLabel[reason] || reason}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function BacktestCard() {
  const { symbol, interval } = useSettingsStore();
  const [equity, setEquity] = useState("10000");
  const [leverage, setLeverage] = useState("1");
  const [startTime, setStartTime] = useState(defaultStartTime);
  const [endTime, setEndTime] = useState(defaultEndTime);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const equityVal = Number(equity) || 10000;
      const tradeAmount = Math.max(MIN_TRADE_AMOUNT, equityVal * TRADE_FRACTION);
      const params: Record<string, unknown> = {
        symbol,
        interval,
        strategy: STRATEGY,
        initial_equity_usdt: equityVal,
        fee_bps: FEE_BPS,
        leverage: Math.min(100, Math.max(1, Number(leverage) || 1)),
        trade_amount_usdt: tradeAmount,
      };
      if (startTime) {
        params.start_time_ms = new Date(startTime).getTime();
      }
      if (endTime) {
        params.end_time_ms = new Date(endTime).getTime();
      }
      const r = await postBacktestQuick(params as any);
      setResult(r);
    } catch (e: any) {
      setError(e.message || "回测失败");
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics;
  const retPct = m ? m.total_return_fraction * 100 : 0;
  const ddPct = m ? m.max_drawdown_fraction * 100 : 0;
  const closedTrades = result?.closed_trades || [];
  const intervalMin = INTERVAL_MINUTES[interval] || 1;
  const ivLabel = INTERVAL_LABEL[interval] || interval;
  const equityVal = Number(equity) || 10000;
  const perTrade = Math.max(MIN_TRADE_AMOUNT, equityVal * TRADE_FRACTION);

  return (
    <Disclosure>
      <Card className="bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div className="font-bold text-sm px-3 py-2 cursor-pointer hover:text-accent transition-colors">
            演示回测
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-2">
            <p className="text-[11px] text-text-muted leading-relaxed">
              {symbol} · {ivLabel} · 多空 · 简化信号撮合，非业绩承诺。
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Input aria-label="投入金额" placeholder="投入金额 USDT" type="number" value={equity} onChange={(e) => setEquity(e.target.value)} className="text-sm" />
              <Input aria-label="杠杆" placeholder="杠杆 (1-100)" type="number" value={leverage} onChange={(e) => setLeverage(e.target.value)} className="text-sm" />
              <Input aria-label="开始时间" type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="text-sm" />
              <Input aria-label="结束时间" type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} className="text-sm" />
            </div>
            <div className="text-[10px] text-text-muted">
              每笔保证金 {perTrade.toFixed(0)} U（投入金额 × {TRADE_FRACTION * 100}%）· 手续费 {FEE_BPS / 100}%
            </div>
            <Button size="sm" variant="primary" className="w-full" onPress={run} isDisabled={loading}>
              {loading ? "运行中…" : "运行回测"}
            </Button>
            {error && <div className="text-xs text-danger">{error}</div>}

            {result && (
              <>
                {result.trade_log.length > 0 && (
                  <div className="rounded bg-white/[0.02] p-2">
                    <div className="text-[10px] text-text-muted mb-1">权益曲线</div>
                    <EquityChart trades={result.trade_log} />
                  </div>
                )}

                {closedTrades.length > 0 && (
                  <details open>
                    <summary className="cursor-pointer hover:text-accent text-[11px] text-text-muted mb-1">
                      交易明细（{closedTrades.length} 笔）
                    </summary>
                    <TradeTable trades={closedTrades} tradeLog={result.trade_log} intervalMinutes={intervalMin} />
                  </details>
                )}

                {m && (
                  <div className="text-[11px] space-y-0.5 mt-2 p-2 rounded bg-white/[0.03]">
                    <div className="flex justify-between">
                      <span className="text-text-muted">K 线根数</span>
                      <span className="font-medium">{m.bars_used}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">总收益</span>
                      <span className={`font-bold ${retPct >= 0 ? "text-success" : "text-danger"}`}>{retPct >= 0 ? "+" : ""}{retPct.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">最大回撤</span>
                      <span className="font-medium text-danger">{ddPct.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">最终权益</span>
                      <span className="font-medium">{m.final_equity_usdt.toFixed(2)} U</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">交易次数</span>
                      <span className="font-medium">{m.trades}</span>
                    </div>
                    {m.win_rate != null && (
                      <div className="flex justify-between">
                        <span className="text-text-muted">胜率</span>
                        <span className="font-medium">{(m.win_rate * 100).toFixed(1)}%</span>
                      </div>
                    )}
                    {m.profit_factor != null && (
                      <div className="flex justify-between">
                        <span className="text-text-muted">盈亏比</span>
                        <span className="font-medium">{m.profit_factor.toFixed(2)}</span>
                      </div>
                    )}
                    {m.sharpe_naive != null && (
                      <div className="flex justify-between">
                        <span className="text-text-muted">Sharpe</span>
                        <span className="font-medium">{m.sharpe_naive.toFixed(2)}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-text-muted">止损触发</span>
                      <span className="font-medium">{m.stop_loss_hits}</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
