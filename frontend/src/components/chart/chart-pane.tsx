import { useAnalysisStore } from "@/stores/analysis-store";
import { EChartsChart } from "./echarts-chart";
import { ChartPlaceholder } from "./chart-placeholder";

export function ChartPane() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const analyzing = useAnalysisStore((s) => s.analyzing);
  const error = useAnalysisStore((s) => s.error);

  return (
    <div className="relative overflow-hidden flex-1 min-h-0 min-w-0">
      {!lastResult && !error && <ChartPlaceholder />}
      <EChartsChart />
      {analyzing && (
        <div className="absolute inset-x-0 top-0 h-[3px] z-50 overflow-hidden">
          <div className="h-full w-1/3 bg-gradient-to-r from-transparent via-accent to-transparent animate-[analyze-scan_1.2s_ease-in-out_infinite]" />
        </div>
      )}
    </div>
  );
}
