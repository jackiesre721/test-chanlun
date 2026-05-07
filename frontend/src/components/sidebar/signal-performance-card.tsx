import { Card, CardContent } from "@heroui/react";

export function SignalPerformanceCard() {
  return (
    <Card className="bg-bg-card border border-border-subtle border-dashed border-accent/20 opacity-60">
      <div className="section-label">信号表现追踪</div>
      <CardContent className="px-3 pb-3">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] text-accent/70 font-medium">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent/40" />
              开发中
            </span>
          </div>
          {/* Skeleton preview */}
          <div className="space-y-1.5">
            <div className="h-2.5 bg-surface-hover rounded w-2/3" />
            <div className="flex gap-2">
              <div className="h-2 bg-surface-hover rounded w-1/4" />
              <div className="h-2 bg-surface-hover rounded w-1/4" />
              <div className="h-2 bg-surface-hover rounded w-1/4" />
            </div>
            <div className="h-2 bg-surface-hover rounded w-1/2" />
          </div>
          <p className="text-[10px] text-text-muted leading-relaxed">
            按买卖点类型统计胜率、筛选信号、历史事件列表。
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
