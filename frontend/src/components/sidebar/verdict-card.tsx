import { useEffect, useRef, useState } from "react";
import { Card, CardContent, Checkbox } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useGlmStore } from "@/stores/glm-store";
import { fmtPrice } from "@/lib/format";
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
      bullets.push(`未完成笔：${dir} ${fmtPrice(sp)} → ${fmtPrice(ep)}`);
    }
  }
  if (lastSignal && lastSignal.price != null && Number.isFinite(Number(lastSignal.price))) {
    bullets.push(`最近信号：${lastSignal.side} ${lastSignal.kind} @ ${fmtPrice(lastSignal.price)}`);
  }

  return { tone, headline, bullets, lastSignal };
}

function parseVerdictSections(raw: string) {
  const lines = raw.split("\n").filter((l) => l.trim());
  const sections: { type: "key" | "bullet" | "meta" | "text"; content: string }[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^来源[：:]/.test(trimmed) || /^说明[：:]/.test(trimmed) || /^参考价位/.test(trimmed) || /^—/.test(trimmed)) {
      sections.push({ type: "meta", content: trimmed });
    } else if (/^[•\-·]/.test(trimmed) || /^\d+[.、]/.test(trimmed)) {
      sections.push({ type: "bullet", content: trimmed.replace(/^[•\-·]\s*/, "") });
    } else if (/关键|价位|止损|止盈|观察价|锚点/.test(trimmed) && trimmed.length < 80) {
      sections.push({ type: "key", content: trimmed });
    } else {
      sections.push({ type: "text", content: trimmed });
    }
  }
  return sections;
}

const TONE_STYLES: Record<string, { pill: string; dot: string }> = {
  bull: { pill: "bg-positive/15 text-positive border-positive/30", dot: "bg-positive" },
  bear: { pill: "bg-negative/15 text-negative border-negative/30", dot: "bg-negative" },
  hold: { pill: "bg-surface-hover text-text-muted border-border-subtle", dot: "bg-text-muted" },
  warn: { pill: "bg-warning/15 text-warning border-warning/30", dot: "bg-warning" },
};

const GLM_COLLAPSE_THRESHOLD = 3;

export function VerdictCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const error = useAnalysisStore((s) => s.error);
  const { useGlm, setUseGlm, verdict, loading, fetchVerdict, clearVerdict } = useGlmStore();
  const abortRef = useRef<AbortController | null>(null);
  const [glmExpanded, setGlmExpanded] = useState(false);

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
        <div className="section-label">当下结论</div>
        <CardContent className="px-3 pb-3 text-xs text-text-muted">
          分析后将展示偏多/偏空/观望结论、要点与 AI 摘要。
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-bg-card border border-border-subtle">
        <div className="section-label">当下结论</div>
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
  const style = TONE_STYLES[v.tone];

  const glmSections = verdict?.raw ? parseVerdictSections(verdict.raw) : [];
  const visibleSections = glmExpanded ? glmSections : glmSections.slice(0, GLM_COLLAPSE_THRESHOLD);
  const hasMoreGlm = glmSections.length > GLM_COLLAPSE_THRESHOLD;

  return (
    <Card className={`card-verdict ${lastResult ? "animate-slide-up" : ""}`} data-tone={v.tone}>
      <div className="section-label flex items-center justify-between" style={{ padding: "2px 0 6px" }}>
        <span>当下结论</span>
        <Checkbox aria-label="启用智谱 GLM 摘要" isSelected={useGlm} onChange={() => setUseGlm(!useGlm)}>
          <span className="text-[10px]">GLM</span>
        </Checkbox>
      </div>
      <CardContent className="px-0 pb-0 pt-0">
        <div className="flex items-center gap-2 mb-2.5">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-sm font-semibold num ${style.pill}`}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${style.dot}`} />
            {v.headline}
          </span>
        </div>

        {v.bullets.map((b, i) => (
          <div key={i} className="text-xs text-text-primary/80 mb-1 flex gap-1.5">
            <span className="text-text-muted shrink-0">•</span>
            <span>{b}</span>
          </div>
        ))}

        {loading && <div className="text-xs text-text-muted mt-2 animate-pulse">GLM 摘要加载中…</div>}

        {glmSections.length > 0 && (
          <div className="mt-2 p-2.5 rounded-lg bg-surface-accent border border-border-subtle text-xs leading-relaxed space-y-1.5">
            {visibleSections.map((sec, i) => {
              if (sec.type === "bullet") {
                return (
                  <div key={i} className="flex gap-1.5 text-text-primary/85">
                    <span className="text-accent shrink-0 mt-px">›</span>
                    <span>{sec.content}</span>
                  </div>
                );
              }
              if (sec.type === "key") {
                return (
                  <div key={i} className="text-text-primary font-medium py-0.5">
                    {sec.content}
                  </div>
                );
              }
              if (sec.type === "meta") {
                return (
                  <div key={i} className="text-text-muted text-[11px] border-t border-border-subtle pt-1.5 mt-1.5">
                    {sec.content}
                  </div>
                );
              }
              return (
                <div key={i} className="text-text-primary/80">{sec.content}</div>
              );
            })}
            {hasMoreGlm && (
              <button
                type="button"
                className="text-[10px] text-accent hover:text-accent/80 transition-colors"
                onClick={() => setGlmExpanded(!glmExpanded)}
              >
                {glmExpanded ? "收起" : `展开全文（+${glmSections.length - GLM_COLLAPSE_THRESHOLD}）`}
              </button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
