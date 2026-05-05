import { useState } from "react";
import { Card, CardContent, Input, Select, ListBox, Button } from "@heroui/react";
import { Disclosure, DisclosureTrigger, DisclosureContent } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { postBacktestQuick } from "@/lib/api";
import type { BacktestResult } from "@/types/analysis";

const STRATEGIES = [
  { value: "long_only_flip", label: "long_only_flip（仅多）" },
  { value: "long_short_flip", label: "long_short_flip（多空）" },
];

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

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await postBacktestQuick({
        symbol: btSymbol || symbol,
        interval: Number(btInterval || interval),
        max_bars: Number(maxBars),
        strategy,
        fee_bps: Number(feeBps),
        initial_equity: Number(equity),
      });
      setResult(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

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
              简化信号撮合 + 手续费假设；仅供<b>假设检验</b>，非业绩承诺。
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Input aria-label="演示回测品种" placeholder="品种" value={btSymbol} onChange={(e) => setBtSymbol(e.target.value)} className="text-sm" />
              <Input aria-label="演示回测周期码" placeholder="周期码" value={btInterval} onChange={(e) => setBtInterval(e.target.value)} className="text-sm" />
              <Input aria-label="演示回测 K 线根数" placeholder="bars" type="number" value={maxBars} onChange={(e) => setMaxBars(e.target.value)} className="text-sm" />
              <Select
                aria-label="演示回测策略"
                selectedKey={strategy}
                onSelectionChange={(key) => key && setStrategy(key as string)}
              >
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
              <div className="text-xs space-y-1 mt-2 p-2 rounded bg-white/[0.03]">
                <div>总收益：<b className={result.total_return_pct >= 0 ? "text-success" : "text-danger"}>{result.total_return_pct.toFixed(2)}%</b></div>
                <div>最大回撤：<b className="text-danger">{result.max_drawdown_pct.toFixed(2)}%</b></div>
                {result.sharpe_ratio != null && <div>Sharpe：{result.sharpe_ratio.toFixed(2)}</div>}
                <div>交易次数：{result.trade_count}</div>
              </div>
            )}
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
