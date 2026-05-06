import { useMemo } from "react";
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
  const {
    sizing_mode,
    equity,
    fraction,
    fixed_quantity,
    entry,
    stop,
    leverage,
    result,
    error,
    computing,
    setSizingMode,
    setEquity,
    setFraction,
    setFixedQuantity,
    setEntry,
    setStop,
    setLeverage,
    compute,
  } = useRiskStore();
  const lastResult = useAnalysisStore((s) => s.lastResult);

  const fillFromChart = () => {
    if (lastResult?.current_price) {
      setEntry(String(lastResult.current_price));
    }
  };

  const fixedPreview = useMemo(() => {
    if (sizing_mode !== "fixed_quantity") return null;
    const qty = Number(fixed_quantity);
    const en = Number(entry);
    const lev = leverage;
    if (!qty || qty <= 0 || !Number.isFinite(en) || en <= 0 || !lev || lev <= 0) return null;
    const notional = qty * en;
    const margin = notional / lev;
    const st = Number(stop);
    const riskAtStop =
      st && Number.isFinite(st) && Math.abs(en - st) > 1e-12 ? qty * Math.abs(en - st) : null;
    return { notional, margin, riskAtStop };
  }, [sizing_mode, fixed_quantity, entry, stop, leverage]);

  const modeClass = (active: boolean) =>
    active
      ? "bg-surface-accent text-accent border-accent/35 font-semibold"
      : "bg-surface-hover border-border-subtle text-text-muted";

  return (
    <Disclosure defaultExpanded>
      <Card className="card-glow bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div className="section-label cursor-pointer hover:text-accent transition-colors" style={{ padding: "10px 12px 8px" }}>
            风控试算（头寸）
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-2">
            <p className="text-[11px] text-text-muted leading-relaxed">
              合约口径数量 / 保证金试算。<b>非投资建议。</b>
            </p>

            <div className="flex flex-wrap gap-1" role="tablist" aria-label="头寸计算模式">
              <button
                type="button"
                role="tab"
                aria-selected={sizing_mode === "risk_fraction"}
                className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${modeClass(sizing_mode === "risk_fraction")}`}
                onClick={() => setSizingMode("risk_fraction")}
              >
                按风险比例
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={sizing_mode === "fixed_quantity"}
                className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${modeClass(sizing_mode === "fixed_quantity")}`}
                onClick={() => setSizingMode("fixed_quantity")}
              >
                固定数量 + 杠杆
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {sizing_mode === "risk_fraction" ? (
                <>
                  <Input
                    aria-label="账户权益（USDT）"
                    placeholder="权益 USDT"
                    type="number"
                    value={equity}
                    onChange={(e) => setEquity(e.target.value)}
                    className="text-sm"
                  />
                  <Input
                    aria-label="单笔最大亏损占净值比例（如 0.01）"
                    placeholder="风险比例 (如 0.01)"
                    type="number"
                    value={fraction}
                    onChange={(e) => setFraction(e.target.value)}
                    title="单笔最大亏损占净值比例"
                    className="text-sm"
                  />
                </>
              ) : (
                <Input
                  aria-label="固定持仓数量（标的数量）"
                  placeholder="固定数量（如 0.01 BTC）"
                  type="number"
                  value={fixed_quantity}
                  onChange={(e) => setFixedQuantity(e.target.value)}
                  className="text-sm col-span-2"
                />
              )}
              <Input
                aria-label="入场价（风控试算）"
                placeholder="入场价"
                type="number"
                value={entry}
                onChange={(e) => setEntry(e.target.value)}
                className="text-sm"
              />
              <Input
                aria-label="止损价（风控试算）"
                placeholder="止损价"
                type="number"
                value={stop}
                onChange={(e) => setStop(e.target.value)}
                className="text-sm"
              />
            </div>

            <Select
              aria-label="杠杆倍数（风控试算）"
              selectedKey={String(leverage)}
              onSelectionChange={(key) => key && setLeverage(Number(key))}
            >
              <Select.Trigger>
                <Select.Value />
              </Select.Trigger>
              <Select.Popover>
                <ListBox>
                  {LEVERAGE_OPTIONS.map((o) => (
                    <ListBox.Item key={o.value} id={o.value}>{o.label}</ListBox.Item>
                  ))}
                </ListBox>
              </Select.Popover>
            </Select>

            {sizing_mode === "fixed_quantity" && fixedPreview && (
              <div className="text-xs space-y-1 p-2 rounded bg-surface-hover border border-accent/15">
                <div>
                  名义价值：<b>{fixedPreview.notional.toFixed(2)}</b> USDT
                </div>
                <div>
                  预估保证金（名义/杠杆）：<b>{fixedPreview.margin.toFixed(2)}</b> USDT
                </div>
                {fixedPreview.riskAtStop != null && (
                  <div className="text-warning">
                    若触发止损价差：约亏 <b>{fixedPreview.riskAtStop.toFixed(2)}</b> USDT（线性近似）
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2 flex-wrap items-center">
              <Button size="sm" variant="ghost" onPress={fillFromChart}>
                填入现价
              </Button>
              {sizing_mode === "risk_fraction" ? (
                <Button size="sm" variant="primary" onPress={compute} isDisabled={computing}>
                  {computing ? "计算中…" : "计算"}
                </Button>
              ) : (
                <span className="text-[10px] text-text-muted">固定数量模式：上方数值实时推算名义与保证金。</span>
              )}
            </div>

            <p className="text-[10px] text-text-muted opacity-80">
              DCA 分批加仓将在后续版本单独建模。
            </p>

            {error && sizing_mode === "risk_fraction" && (
              <div className="text-xs text-negative">{error}</div>
            )}
            {result && sizing_mode === "risk_fraction" && (
              <div className="text-xs space-y-1 mt-2 p-2 rounded bg-surface-hover">
                <div>
                  数量：<b>{result.quantity?.toFixed(6)}</b>
                </div>
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
