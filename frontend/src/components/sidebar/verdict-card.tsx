import { useEffect, useRef } from "react";
import { Card, CardHeader, CardContent, Checkbox, Chip } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useGlmStore } from "@/stores/glm-store";
import { ANALYZE_LIMIT } from "@/constants/chart-palette";

function computeVerdict(result: NonNullable<ReturnType<typeof useAnalysisStore.getState>["lastResult"]>) {
  const buys = result.buy_signals || [];
  const sells = result.sell_signals || [];
  const lastSignal = [...buys, ...sells].sort((a, b) => b.idx - a.idx)[0];
  const activeBi = result.active_bi;
  let tone: "bull" | "bear" | "hold" | "warn" = "hold";
  let headline = "观望";
  const bullets: string[] = [];

  if (lastSignal?.side === "BUY") { tone = "bull"; headline = "偏多"; }
  else if (lastSignal?.side === "SELL") { tone = "bear"; headline = "偏空"; }

  if (activeBi) {
    const sp = activeBi.start_price;
    const ep = activeBi.end_price;
    if (sp != null && ep != null && Number.isFinite(Number(sp)) && Number.isFinite(Number(ep))) {
      const dir = activeBi.direction === "UP" || activeBi.direction === "up" ? "上升" : "下降";
      bullets.push(`未完成笔：${dir} ${Number(sp).toFixed(2)} → ${Number(ep).toFixed(2)}`);
    }
  }
  if (lastSignal && lastSignal.price != null && Number.isFinite(Number(lastSignal.price))) {
    bullets.push(`最近信号：${lastSignal.side} ${lastSignal.kind} @ ${Number(lastSignal.price).toFixed(2)}`);
  }

  const toneColor: Record<string, string> = { bull: "success", bear: "danger", hold: "default", warn: "warning" };
  return { tone, headline, bullets, chipColor: toneColor[tone] as "success" | "danger" | "default" | "warning" };
}

export function VerdictCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);
  const { useGlm, setUseGlm, verdict, loading, fetchVerdict, clearVerdict } = useGlmStore();
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    if (lastResult && useGlm) {
      const ac = new AbortController();
      abortRef.current = ac;
      fetchVerdict(lastResult, ac.signal);
    } else {
      clearVerdict();
    }
    return () => { abortRef.current?.abort(); };
  }, [lastResult, useGlm]);

  if (!lastResult && !error) {
    return (
      <Card className="bg-bg-card border border-border-subtle">
        <CardHeader className="font-bold text-sm px-3 py-2">当下简要结论</CardHeader>
        <CardContent className="px-3 pb-3 text-xs text-text-muted">
          分析后将展示偏多/偏空/观望结论、要点与 AI 摘要。
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-bg-card border border-border-subtle">
        <CardHeader className="font-bold text-sm px-3 py-2">当下简要结论</CardHeader>
        <CardContent className="px-3 pb-3">
          <span className="text-negative text-xs">{error}</span>
          <div className="text-[11px] text-text-muted mt-2 leading-relaxed">
            可尝试：检查网络与后端健康；切换品种或周期；确认网关把 POST /analyze 指到本服务。
          </div>
        </CardContent>
      </Card>
    );
  }

  const v = computeVerdict(lastResult!);

  return (
    <Card className="bg-bg-card border border-border-subtle">
      <CardHeader className="font-bold text-sm px-3 py-2 flex items-center justify-between">
        <span>当下简要结论</span>
        <Checkbox size="sm" aria-label="启用智谱 GLM 摘要" isSelected={useGlm} onChange={() => setUseGlm(!useGlm)}>
          智谱 GLM 摘要
        </Checkbox>
      </CardHeader>
      <CardContent className="px-3 pb-3">
        <div className="flex items-center gap-2 mb-2">
          <Chip color={v.chipColor} size="sm" variant="flat">{v.headline}</Chip>
        </div>
        {v.bullets.map((b, i) => (
          <div key={i} className="text-xs text-text-primary/80 mb-1">• {b}</div>
        ))}
        {loading && <div className="text-xs text-text-muted mt-2 animate-pulse">GLM 摘要加载中…</div>}
        {verdict?.raw && (
          <div className="mt-2 p-2 rounded-lg bg-accent/5 border border-accent/10 text-xs text-text-primary/70 whitespace-pre-wrap">
            {verdict.raw}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
