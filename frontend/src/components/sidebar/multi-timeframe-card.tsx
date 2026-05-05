import { useState } from "react";
import { Card, CardContent, Button, Chip } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { postMultiAnalyze } from "@/lib/api";
import { fmtOpenTime } from "@/lib/format";
import type { AnalyzeResult } from "@/types/analysis";

function intervalLabel(iv: string) {
  const m: Record<string, string> = { "1": "1m", "15": "15m", "30": "30m", "60": "1h", "240": "4h", "1440": "1d" };
  return m[iv] || iv;
}

function briefVerdict(r: AnalyzeResult) {
  const buys = r.buy_signals?.length || 0;
  const sells = r.sell_signals?.length || 0;
  if (buys > sells) return { text: "偏多", color: "success" as const };
  if (sells > buys) return { text: "偏空", color: "danger" as const };
  return { text: "观望", color: "default" as const };
}

export function MultiTimeframeCard() {
  const symbol = useSettingsStore((s) => s.symbol);
  const setInterval = useSettingsStore((s) => s.setInterval);
  const analyze = useAnalysisStore((s) => s.analyze);
  const [results, setResults] = useState<Record<string, AnalyzeResult> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const intervals = ["1", "15", "60", "240", "1440"];

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await postMultiAnalyze(symbol, intervals);
      setResults(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const openInChart = (iv: string) => {
    setInterval(iv);
    analyze(symbol, iv);
  };

  return (
    <Card className="card-glow bg-bg-card border border-border-subtle">
      <div className="section-label">多周期摘要</div>
      <CardContent className="px-3 pb-3 text-xs text-text-muted">
        <p className="text-[11px] leading-relaxed mb-2">
          并行请求多个周期。「主图打开」将切换周期并重新分析。
        </p>
        <Button size="sm" color="primary" onPress={load} isDisabled={loading} className="mb-2">
          {loading ? "加载中…" : "加载多周期表"}
        </Button>
        {error && <div className="text-negative mb-2">{error}</div>}
        {results && (
          <div className="space-y-1.5">
            {intervals.map((iv) => {
              const r = results[iv];
              if (!r) return null;
              const v = briefVerdict(r);
              return (
                <div key={iv} className="flex items-center gap-2 p-1.5 rounded bg-surface-hover">
                  <span className="font-mono w-8">{intervalLabel(iv)}</span>
                  <Chip size="sm" variant="flat" color={v.color}>{v.text}</Chip>
                  <span className="text-[10px]">笔{r.bis?.length || 0} 段{r.segments?.length || 0}</span>
                  <Button size="sm" variant="light" className="ml-auto text-[10px]" onPress={() => openInChart(iv)}>
                    主图打开
                  </Button>
                </div>
              );
            })}
          </div>
        )}
        {!results && !loading && <span className="text-text-muted">尚未加载</span>}
      </CardContent>
    </Card>
  );
}
