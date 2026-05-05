import { Card, CardContent } from "@heroui/react";

/** P3：占位卡片；后续接入 IndexedDB / 后端记录信号结算后再填数据。 */
export function SignalPerformanceCard() {
  return (
    <Card className="card-glow bg-bg-card border border-border-subtle border-dashed border-accent/25">
      <div className="section-label">信号表现追踪</div>
      <CardContent className="px-3 pb-3 text-[11px] text-text-muted leading-relaxed space-y-2">
        <p>
          规划能力：按买卖点类型统计胜率与期望；记录每次信号的后续结果（手动或规则自动结算）。
        </p>
        <p className="text-accent/90 font-semibold">即将接入 · 当前无历史样本</p>
        <p className="opacity-70">
          实现后将支持：筛选 <span className="font-mono text-[10px]">first / second / third …</span>、
          小表汇总、最近事件列表。
        </p>
      </CardContent>
    </Card>
  );
}
