import { Card, CardHeader, CardContent } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import type { AnalyzeResult } from "@/types/analysis";

function fmtPx(n: unknown): string {
  const x = Number(n);
  return Number.isFinite(x) ? x.toFixed(2) : "—";
}

function lookupSignalPrice(result: AnalyzeResult, idx: number): number | undefined {
  const all = [...(result.buy_signals || []), ...(result.sell_signals || [])];
  return all.find((s) => s.idx === idx)?.price;
}

function relationZh(rel: string): string {
  const m: Record<string, string> = {
    inside: "在内",
    above: "在上沿之上",
    below: "在下沿之下",
    none: "无中枢参照",
  };
  return m[rel] ?? rel;
}

function buildFocusHtml(result: AnalyzeResult): string[] | null {
  const af = result.action_focus;
  if (!af) return null;
  const lines: string[] = [];

  const pxBase = af.current_price ?? result.current_price ?? af.price;
  if (pxBase != null && Number.isFinite(Number(pxBase))) {
    lines.push(`当前价位：<b>${fmtPx(pxBase)}</b>`);
  }

  if (af.active_bi) {
    const dir =
      af.active_bi.direction === "UP" || af.active_bi.direction === "up"
        ? "上升"
        : "下降";
    lines.push(
      `未完成笔：${dir} ${fmtPx(af.active_bi.start_price)} → ${fmtPx(af.active_bi.end_price)}`,
    );
  } else {
    lines.push("暂无未完成笔");
  }

  const pp = af.primary_pivot;
  if (pp) {
    const ref = pp.pivot;
    if (ref && ref.zd != null && ref.zg != null) {
      lines.push(
        `本级中枢 [${fmtPx(ref.zd)}, ${fmtPx(ref.zg)}]：${relationZh(pp.relation)}`,
      );
    } else {
      lines.push(`本级中枢：${relationZh(pp.relation)}（暂无 ZD/ZG 引用）`);
    }
  }

  const hp = af.higher_pivot;
  if (hp) {
    const ref = hp.pivot;
    if (ref && ref.zd != null && ref.zg != null) {
      lines.push(
        `上级中枢 [${fmtPx(ref.zd)}, ${fmtPx(ref.zg)}]：${relationZh(hp.relation)}`,
      );
    } else {
      lines.push(`上级中枢：${relationZh(hp.relation)}（暂无 ZD/ZG 引用）`);
    }
  }

  const rd = af.recent_divergence;
  if (rd) {
    const ratio = rd.ratio ?? rd.macd_ratio;
    const ratioStr = ratio != null && Number.isFinite(Number(ratio)) ? fmtPx(ratio) : "—";
    lines.push(
      `近期背驰：${rd.level} ${rd.direction} strength=${ratioStr}${rd.structure_kind ? ` (${rd.structure_kind})` : ""}`,
    );
  } else {
    lines.push("未发现近期背驰");
  }

  const rs = af.recent_signal;
  if (rs) {
    const p =
      rs.price != null && Number.isFinite(Number(rs.price))
        ? Number(rs.price)
        : lookupSignalPrice(result, rs.idx);
    lines.push(
      `最近信号：${rs.side} ${rs.kind} @ ${p != null ? fmtPx(p) : "—"}（idx=${rs.idx}）`,
    );
  } else {
    lines.push("当前无可操作信号 — 非投资建议");
  }

  return lines;
}

export function ActionFocusCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);

  const lines = lastResult ? buildFocusHtml(lastResult) : null;

  return (
    <Card className="bg-bg-card border border-border-subtle">
      <CardHeader className="font-bold text-sm px-3 py-2">当下关注点（可操作语境）</CardHeader>
      <CardContent className="px-3 pb-3 text-xs text-text-muted">
        {error ? (
          <span className="text-negative">{error}</span>
        ) : lines ? (
          <div className="space-y-1">
            {lines.map((l, i) => (
              <div key={i} dangerouslySetInnerHTML={{ __html: l }} />
            ))}
          </div>
        ) : (
          "分析后显示当前价位、未完成笔方向、中枢位置与近期背驰。"
        )}
      </CardContent>
    </Card>
  );
}
