import { Card, CardHeader, CardContent } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { ANALYZE_LIMIT } from "@/constants/chart-palette";

export function ExplanationCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);

  return (
    <Card className="bg-bg-card border border-border-subtle">
      <CardHeader className="font-bold text-sm px-3 py-2">说明</CardHeader>
      <CardContent className="px-3 pb-3 text-xs text-text-muted">
        <div>分析链路：分型 → 笔 → 线段 → 中枢 → 背驰 → 买卖点。结构不足或无离开段背驰证据时不强行给点。</div>
        {lastResult && (
          <div className="mt-2 text-[11px] text-text-primary/50">
            数据来自 {lastResult.data_source || "API"}；规则版本 {lastResult.rules_version || "unknown"}；
            线段 {lastResult.segment_engine === "strict67" ? "67课特征序列(strict67)" : "legacy三笔重叠"}；
            本次响应 <b>{lastResult.kline_data.length}</b> 根合并 K（请求 limit=<b>{ANALYZE_LIMIT}</b>）。
          </div>
        )}
        {lastResult?.warning && (
          <div className="mt-2 text-warning text-[11px]">{lastResult.warning}</div>
        )}
      </CardContent>
    </Card>
  );
}
