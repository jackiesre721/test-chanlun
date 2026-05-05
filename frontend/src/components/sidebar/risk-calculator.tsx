import { Card, CardContent, Input, Select, ListBox, Button } from "@heroui/react";
import { Disclosure, DisclosureTrigger, DisclosureContent } from "@heroui/react";
import { useRiskStore } from "@/stores/risk-store";
import { useAnalysisStore } from "@/stores/analysis-store";

const LEVERAGE_OPTIONS = [
  { value: "1", label: "1x（现货）" },
  { value: "2", label: "2x" },
  { value: "3", label: "3x" },
  { value: "5", label: "5x" },
  { value: "7", label: "7x" },
  { value: "10", label: "10x" },
];

export function RiskCalculator() {
  const { equity, fraction, entry, stop, leverage, result, error, computing,
    setEquity, setFraction, setEntry, setStop, setLeverage, compute } = useRiskStore();
  const lastResult = useAnalysisStore((s) => s.lastResult);

  const fillFromChart = () => {
    if (lastResult?.current_price) {
      setEntry(String(lastResult.current_price));
    }
  };

  return (
    <Disclosure defaultOpen>
      <Card className="bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div className="font-bold text-sm px-3 py-2 cursor-pointer hover:text-accent transition-colors">
            风控试算（头寸）
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-2">
            <p className="text-[11px] text-text-muted leading-relaxed">
              给定单笔风险比例与止损价差，估算合约口径数量与保证金。<b>非投资建议。</b>
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Input aria-label="账户权益（USDT）" placeholder="权益 USDT" type="number" value={equity} onChange={(e) => setEquity(e.target.value)} className="text-sm" />
              <Input aria-label="单笔最大亏损占净值比例（如 0.01）" placeholder="风险比例 (如 0.01)" type="number" value={fraction} onChange={(e) => setFraction(e.target.value)}
                title="单笔最大亏损占净值比例" className="text-sm" />
              <Input aria-label="入场价（风控试算）" placeholder="入场价" type="number" value={entry} onChange={(e) => setEntry(e.target.value)} className="text-sm" />
              <Input aria-label="止损价（风控试算）" placeholder="止损价" type="number" value={stop} onChange={(e) => setStop(e.target.value)} className="text-sm" />
            </div>
            <Select
              aria-label="杠杆倍数（风控试算）"
              selectedKey={String(leverage)}
              onSelectionChange={(key) => key && setLeverage(Number(key))}
            >
              <Select.Trigger>
                <Select.Value placeholder="杠杆" />
              </Select.Trigger>
              <Select.Popover>
                <ListBox>
                  {LEVERAGE_OPTIONS.map((o) => (
                    <ListBox.Item key={o.value} id={o.value}>{o.label}</ListBox.Item>
                  ))}
                </ListBox>
              </Select.Popover>
            </Select>
            <div className="flex gap-2">
              <Button size="sm" variant="light" onPress={fillFromChart}>填入现价</Button>
              <Button size="sm" color="primary" onPress={compute} isDisabled={computing}>
                {computing ? "计算中…" : "计算"}
              </Button>
            </div>
            {error && <div className="text-xs text-negative">{error}</div>}
            {result && (
              <div className="text-xs space-y-1 mt-2 p-2 rounded bg-white/[0.03]">
                <div>数量：<b>{result.quantity?.toFixed(6)}</b></div>
                <div>名义值：{result.notional?.toFixed(2)} USDT</div>
                <div>杠杆：{result.leverage}x</div>
                {result.required_margin && <div>所需保证金：{result.required_margin.toFixed(2)} USDT</div>}
                {result.liquidation_price && <div>预估强平价：{result.liquidation_price.toFixed(2)}</div>}
                {result.effective_risk_pct && <div>实际风险：{result.effective_risk_pct.toFixed(2)}%</div>}
                {result.warnings?.map((w, i) => (
                  <div key={i} className="text-warning">{w}</div>
                ))}
              </div>
            )}
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
