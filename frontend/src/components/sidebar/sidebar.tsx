import { VerdictCard } from "./verdict-card";
import { ActionFocusCard } from "./action-focus-card";
import { SignalsCard } from "./signals-card";
import { StructureStatusCard } from "./structure-status-card";
import { RiskCalculator } from "./risk-calculator";
import { MultiTimeframeCard } from "./multi-timeframe-card";
import { PaperTradingCard } from "./paper-trading-card";
import { BacktestCard } from "./backtest-card";
import { DisciplineCard } from "./discipline-card";
import { ExplanationCard } from "./explanation-card";
import { AdvancedStructureCard } from "./advanced-structure-card";
import { GlmConfigCard } from "./glm-config-card";

export function Sidebar() {
  return (
    <div className="overflow-y-auto border-l border-border-subtle bg-bg-deep/50 p-3 space-y-3 w-full">
      <VerdictCard />
      <ActionFocusCard />
      <SignalsCard />
      <StructureStatusCard />
      <RiskCalculator />
      <MultiTimeframeCard />
      <PaperTradingCard />
      <BacktestCard />
      <DisciplineCard />
      <ExplanationCard />
      <AdvancedStructureCard />
      <GlmConfigCard />
    </div>
  );
}
