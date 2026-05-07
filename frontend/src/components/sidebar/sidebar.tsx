import { Tabs } from "@heroui/react";
import { useSettingsStore, type SidebarTabKey } from "@/stores/settings-store";
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
import { SignalPerformanceCard } from "./signal-performance-card";

const TAB_PANEL_CLASS =
  "flex-1 min-h-0 overflow-y-auto px-3 py-3 space-y-3.5 outline-none data-[focus-visible=true]:outline-none";

export function Sidebar() {
  const sidebarTab = useSettingsStore((s) => s.sidebarTab);
  const setSidebarTab = useSettingsStore((s) => s.setSidebarTab);

  const onTabChange = (key: unknown) => {
    if (typeof key === "string" && ["now", "risk", "research", "ref"].includes(key)) {
      setSidebarTab(key as SidebarTabKey);
    }
  };

  return (
    <div className="sidebar-panel flex h-full min-h-0 flex-1 flex-col border-l border-border-subtle bg-bg-deep/50">
      <Tabs.Root
        selectedKey={sidebarTab}
        onSelectionChange={onTabChange}
        className="flex flex-1 min-h-0 flex-col"
      >
        <Tabs.ListContainer className="shrink-0 border-b border-border-subtle bg-bg-deep/95 px-2 pt-2 pb-1.5">
          <Tabs.List className="flex flex-wrap gap-0.5">
            <Tabs.Tab id="now" className="sidebar-tab shrink-0">
              当下
            </Tabs.Tab>
            <Tabs.Tab id="risk" className="sidebar-tab shrink-0">
              执行
            </Tabs.Tab>
            <Tabs.Tab id="research" className="sidebar-tab shrink-0">
              研究
            </Tabs.Tab>
            <Tabs.Tab id="ref" className="sidebar-tab shrink-0">
              设置
            </Tabs.Tab>
          </Tabs.List>
        </Tabs.ListContainer>

        <Tabs.Panel id="now" className={TAB_PANEL_CLASS}>
          <VerdictCard />
          <ActionFocusCard />
          <SignalsCard />
          <StructureStatusCard />
        </Tabs.Panel>

        <Tabs.Panel id="risk" className={TAB_PANEL_CLASS}>
          <RiskCalculator />
          <PaperTradingCard />
          <DisciplineCard />
        </Tabs.Panel>

        <Tabs.Panel id="research" className={TAB_PANEL_CLASS}>
          <MultiTimeframeCard />
          <BacktestCard />
          <SignalPerformanceCard />
        </Tabs.Panel>

        <Tabs.Panel id="ref" className={TAB_PANEL_CLASS}>
          <AdvancedStructureCard />
          <ExplanationCard />
          <GlmConfigCard />
        </Tabs.Panel>
      </Tabs.Root>
    </div>
  );
}
