import { useEffect } from "react";
import "@heroui/react/styles";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useSettingsStore } from "@/stores/settings-store";
import { Toolbar } from "@/components/toolbar/toolbar";
import { MainLayout } from "@/components/layout/main-layout";
import { AppFooter } from "@/components/layout/app-footer";
import { LoadingOverlay } from "@/components/layout/loading-overlay";
import { TradingPage } from "@/components/trading/trading-page";

export function App() {
  const analyze = useAnalysisStore((s) => s.analyze);
  const { symbol, interval, viewMode } = useSettingsStore();

  // Analyze when symbol / interval changes (includes initial mount)
  useEffect(() => {
    analyze(symbol, interval);
  }, [symbol, interval, analyze]);

  if (viewMode === "trading") {
    return (
      <div className="flex flex-col h-full">
        <LoadingOverlay />
        <TradingPage />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <Toolbar />
      <MainLayout />
      <AppFooter />
      <LoadingOverlay />
    </div>
  );
}
