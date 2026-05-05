export function ChartPlaceholder() {
  return (
    <div className="absolute inset-0 flex items-center justify-center z-[2] pointer-events-none">
      <div className="text-center opacity-35">
        <div className="text-5xl text-accent/60 mb-3">⟐</div>
        <div className="text-base font-bold tracking-widest text-text-primary/70 mb-2">
          Chanlan 缠论结构终端
        </div>
        <div className="text-xs text-text-muted/50">
          选择品种与周期，点击上方「分析」开始
        </div>
      </div>
    </div>
  );
}
