import { Card, CardHeader, CardContent } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";

export function StructureStatusCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);

  if (!lastResult && !error) {
    return (
      <Card className="bg-bg-card border border-border-subtle">
        <CardHeader className="font-bold text-sm px-3 py-2">结构状态</CardHeader>
        <CardContent className="px-3 pb-3 text-xs text-text-muted">
          分析后显示笔/线段/中枢/背驰统计与走势形态。
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-bg-card border border-border-subtle">
        <CardHeader className="font-bold text-sm px-3 py-2">结构状态</CardHeader>
        <CardContent className="px-3 pb-3"><span className="text-xs text-negative">{error}</span></CardContent>
      </Card>
    );
  }

  const r = lastResult!;
  const lastBi = r.bis[r.bis.length - 1];
  const biPivots = (r.zhongshus || []).filter(p => p.level === "bi").length;
  const segPivots = (r.zhongshus || []).filter(p => p.level === "segment").length;
  const segEngine = r.segment_engine === "strict67" ? "67课特征序列（strict67）" : "legacy（三笔重叠+延伸）";
  const dirLabel = (d: string) => d === "UP" || d === "up" ? "上升" : "下降";

  const stats = [
    [`确认笔数量：${r.bis.length}`],
    [`本级分型数量：${r.fractals.length}`],
    [`线段划分引擎：${segEngine}`],
    [`线段数量：${r.segments.length}`],
    [`笔中枢数量：${biPivots}`],
    [`线段中枢数量：${segPivots}`],
    [`背驰候选：${r.divergences.length}`],
  ];

  return (
    <Card className="bg-bg-card border border-border-subtle">
      <CardHeader className="font-bold text-sm px-3 py-2">结构状态</CardHeader>
      <CardContent className="px-3 pb-3 text-xs space-y-0.5">
        {stats.map(([line], i) => (
          <div key={i} dangerouslySetInnerHTML={{ __html: line.replace(/：(.+)/, "：<b>$1</b>") }} />
        ))}
        {r.lines_form && (
          <div className="mt-2">
            走势形态：<b>{r.lines_form.primary}</b>
            {r.lines_form.detail_zh && ` — ${r.lines_form.detail_zh}`}
          </div>
        )}
        {lastBi && (
          <div className="mt-1">
            最后确认笔：{dirLabel(lastBi.direction)}，{Number(lastBi.start_price).toFixed(2)} → {Number(lastBi.end_price).toFixed(2)}
          </div>
        )}
        {r.active_bi ? (
          <div className="mt-1 text-warning">
            当前未完成笔：{dirLabel(r.active_bi.direction)}，{Number(r.active_bi.start_price).toFixed(2)} → {Number(r.active_bi.end_price).toFixed(2)}
          </div>
        ) : (
          <div className="mt-1">暂无未完成笔。</div>
        )}
      </CardContent>
    </Card>
  );
}
