export function ChartPlaceholder() {
  return (
    <div className="chart-placeholder absolute inset-0 flex items-center justify-center z-[2] pointer-events-none">
      <div className="text-center relative z-10">
        <div className="text-4xl text-accent/30 mb-4 font-mono">⟐</div>
        <div className="text-sm font-semibold tracking-widest text-text-primary/40 mb-2">
          Chanlan 缠论结构终端
        </div>
        <div className="text-xs text-text-muted/30 font-mono">
          选择品种与周期，点击「分析」开始
        </div>
      </div>
    </div>
  );
}
