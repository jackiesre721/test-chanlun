import { Card, CardContent } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { fmtPrice } from "@/lib/format";
import type { AnalyzeResult, ActionFocus } from "@/types/analysis";

function fmtPx(n: unknown): string {
  const x = Number(n);
  return Number.isFinite(x) ? fmtPrice(x) : "—";
}

function relationZh(rel: string): string {
  const m: Record<string, string> = {
    inside: "中枢内",
    above: "中枢上方",
    below: "中枢下方",
    none: "无中枢",
  };
  return m[rel] ?? rel;
}

function relationColor(rel: string): string {
  const m: Record<string, string> = {
    inside: "text-warning",
    above: "text-positive",
    below: "text-negative",
    none: "text-text-muted",
  };
  return m[rel] ?? "text-text-muted";
}

function PivotMiniBar({ zd, zg, price }: { zd: number; zg: number; price: number }) {
  const lo = Math.min(zd, zg, price);
  const hi = Math.max(zd, zg, price);
  const range = hi - lo || 1;
  const leftPct = ((zd - lo) / range) * 100;
  const widthPct = ((zg - zd) / range) * 100;
  const pricePct = ((price - lo) / range) * 100;
  const inRange = price >= zd && price <= zg;

  return (
    <div className="relative h-3 w-full rounded-sm bg-surface-hover overflow-hidden">
      <div
        className="absolute top-0.5 bottom-0.5 rounded-sm bg-accent/20 border border-accent/30"
        style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 2)}%` }}
      />
      <div
        className={`absolute top-0.5 w-1 h-2 rounded-full ${inRange ? "bg-warning" : price < zd ? "bg-negative" : "bg-positive"}`}
        style={{ left: `${Math.min(Math.max(pricePct, 1), 97)}%` }}
      />
    </div>
  );
}

interface FocusData {
  price: number | null;
  activeBiDir: string | null;
  activeBiRange: string | null;
  primaryPivot: { zd: number; zg: number; relation: string } | null;
  higherPivot: { zd: number; zg: number; relation: string } | null;
  divergence: string | null;
  signal: { side: string; kind: string; price: number; sl: number | null; tp1: number | null; tp2: number | null } | null;
}

function extractFocus(result: AnalyzeResult): FocusData | null {
  const af = result.action_focus;
  if (!af) return null;

  const price = af.current_price ?? result.current_price ?? af.price ?? null;
  const numPrice = price != null && Number.isFinite(Number(price)) ? Number(price) : null;

  let activeBiDir: string | null = null;
  let activeBiRange: string | null = null;
  if (af.active_bi) {
    const dir = af.active_bi.direction === "UP" || af.active_bi.direction === "up" ? "↑" : "↓";
    activeBiDir = dir;
    activeBiRange = `${fmtPx(af.active_bi.start_price)} → ${fmtPx(af.active_bi.end_price)}`;
  }

  let primaryPivot: FocusData["primaryPivot"] = null;
  if (af.primary_pivot?.pivot?.zd != null && af.primary_pivot.pivot.zg != null) {
    primaryPivot = {
      zd: Number(af.primary_pivot.pivot.zd),
      zg: Number(af.primary_pivot.pivot.zg),
      relation: af.primary_pivot.relation,
    };
  }

  let higherPivot: FocusData["higherPivot"] = null;
  if (af.higher_pivot?.pivot?.zd != null && af.higher_pivot.pivot.zg != null) {
    higherPivot = {
      zd: Number(af.higher_pivot.pivot.zd),
      zg: Number(af.higher_pivot.pivot.zg),
      relation: af.higher_pivot.relation,
    };
  }

  let divergence: string | null = null;
  if (af.recent_divergence) {
    const rd = af.recent_divergence;
    const ratio = rd.ratio ?? rd.macd_ratio;
    const ratioStr = ratio != null && Number.isFinite(Number(ratio)) ? fmtPx(ratio) : "—";
    divergence = `${rd.level} ${rd.direction} str=${ratioStr}${rd.structure_kind ? ` (${rd.structure_kind})` : ""}`;
  }

  let signal: FocusData["signal"] = null;
  if (af.recent_signal) {
    const rs = af.recent_signal;
    const sp = rs.price != null && Number.isFinite(Number(rs.price)) ? Number(rs.price) : null;
    signal = {
      side: rs.side,
      kind: rs.kind,
      price: sp ?? 0,
      sl: rs.stop_loss != null && Number.isFinite(Number(rs.stop_loss)) ? Number(rs.stop_loss) : null,
      tp1: rs.take_profit_1 != null && Number.isFinite(Number(rs.take_profit_1)) ? Number(rs.take_profit_1) : null,
      tp2: rs.take_profit_2 != null && Number.isFinite(Number(rs.take_profit_2)) ? Number(rs.take_profit_2) : null,
    };
  }

  return { price: numPrice, activeBiDir, activeBiRange, primaryPivot, higherPivot, divergence, signal };
}

export function ActionFocusCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);

  const focus = lastResult ? extractFocus(lastResult) : null;

  return (
    <Card className="card-glow bg-bg-card border border-border-subtle">
      <div className="section-label">当下关注点</div>
      <CardContent className="px-3 pb-3 text-xs">
        {error ? (
          <span className="text-negative">{error}</span>
        ) : focus ? (
          <div className="space-y-2">
            {/* Compact status bar */}
            <div className="flex items-center gap-2 flex-wrap">
              {focus.price != null && (
                <span className="font-mono font-semibold num text-text-primary">{fmtPrice(focus.price)}</span>
              )}
              {focus.activeBiDir && (
                <span className={`text-xs ${focus.activeBiDir === "↑" ? "text-positive" : "text-negative"}`}>
                  未完成笔{focus.activeBiDir}
                </span>
              )}
              {focus.primaryPivot && (
                <span className={`text-xs ${relationColor(focus.primaryPivot.relation)}`}>
                  {relationZh(focus.primaryPivot.relation)}
                </span>
              )}
            </div>

            {/* Active bi range */}
            {focus.activeBiRange && (
              <div className="text-[11px] text-text-muted">
                笔幅 {focus.activeBiRange}
              </div>
            )}

            {/* Primary pivot with mini bar */}
            {focus.primaryPivot && focus.price != null && (
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-text-muted num">
                  <span>本级中枢 [{fmtPrice(focus.primaryPivot.zd)}, {fmtPrice(focus.primaryPivot.zg)}]</span>
                </div>
                <PivotMiniBar zd={focus.primaryPivot.zd} zg={focus.primaryPivot.zg} price={focus.price} />
              </div>
            )}

            {/* Higher pivot */}
            {focus.higherPivot && (
              <div className="text-[11px] text-text-muted">
                上级中枢 [{fmtPrice(focus.higherPivot.zd)}, {fmtPrice(focus.higherPivot.zg)}]
                <span className={`ml-1 ${relationColor(focus.higherPivot.relation)}`}>
                  {relationZh(focus.higherPivot.relation)}
                </span>
              </div>
            )}

            {/* Divergence */}
            {focus.divergence && (
              <div className="text-[11px] text-accent/80">
                背驰 {focus.divergence}
              </div>
            )}

            {/* Signal */}
            {focus.signal && (
              <div className="pt-1 border-t border-border-subtle space-y-0.5">
                <div className="flex items-center gap-1.5">
                  <span className={`text-[10px] font-bold px-1 py-0.5 rounded-sm ${focus.signal.side === "BUY" ? "bg-positive/15 text-positive" : "bg-negative/15 text-negative"}`}>
                    {focus.signal.side === "BUY" ? "▲ BUY" : "▼ SELL"}
                  </span>
                  <span className="text-[11px] text-text-primary/90">{focus.signal.kind}</span>
                  <span className="font-mono text-text-primary num ml-auto">{fmtPrice(focus.signal.price)}</span>
                </div>
                <div className="flex gap-3 text-[10px] num text-text-muted">
                  {focus.signal.sl != null && <span className="text-warning">SL {fmtPrice(focus.signal.sl)}</span>}
                  {focus.signal.tp1 != null && <span className="text-success">TP1 {fmtPrice(focus.signal.tp1)}</span>}
                  {focus.signal.tp2 != null && <span className="text-success">TP2 {fmtPrice(focus.signal.tp2)}</span>}
                </div>
              </div>
            )}
          </div>
        ) : (
          <span className="text-text-muted">分析后显示当前价位、未完成笔方向、中枢位置与近期背驰。</span>
        )}
      </CardContent>
    </Card>
  );
}
