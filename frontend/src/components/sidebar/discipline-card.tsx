import { Card, CardContent, Button, Input, TextArea } from "@heroui/react";
import { Disclosure, DisclosureTrigger, DisclosureContent } from "@heroui/react";
import { useDisciplineStore } from "@/stores/discipline-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useEffect } from "react";

export function DisciplineCard() {
  const { consecutiveLosses, threshold, hypothesisNotes, ruleSnapshot,
    incrementLoss, resetLosses, setThreshold, setHypothesisNotes, updateRuleSnap } = useDisciplineStore();
  const lastResult = useAnalysisStore((s) => s.lastResult);

  useEffect(() => {
    if (lastResult) updateRuleSnap(lastResult);
  }, [lastResult]);

  const thresholdReached = consecutiveLosses >= threshold;

  return (
    <Disclosure>
      <Card className="bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div className="font-bold text-sm px-3 py-2 cursor-pointer hover:text-accent transition-colors">
            交易纪律 · 生存与验证
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-3 text-xs">
            {/* Section 1: Survival */}
            <div>
              <div className="font-bold text-text-primary mb-1">1. 先让自己「不会死」</div>
              <div className="text-[11px] text-text-muted leading-relaxed space-y-1">
                <div>单笔最大亏损：常见实盘自省区间约为净值 <b>0.25%～1%</b>/笔。</div>
                <div>连续回撤熔断：用自检计数记录连续不利结果。</div>
              </div>
              <div className="flex gap-1.5 mt-2 items-center flex-wrap">
                <span className="text-[11px] text-text-muted">单笔风险比例：</span>
                {[0.0025, 0.005, 0.01].map((f) => (
                  <Button key={f} size="sm" variant="light" className="text-[10px]"
                    onPress={() => { /* fill risk fraction — would need risk store */ }}>
                    {(f * 100).toFixed(f < 0.01 ? 2 : 0)}%
                  </Button>
                ))}
              </div>
            </div>

            {/* Section 2: Hypothesis */}
            <div>
              <div className="font-bold text-text-primary mb-1">2. 「信念」→ 假设 — 验证</div>
              <TextArea
                aria-label="交易假设与验证规则笔记"
                placeholder="例：入场=一类买点+离开段背驰证据；离场=反向同级别卖点或止损触发"
                value={hypothesisNotes}
                onChange={(e) => setHypothesisNotes(e.target.value)}
                rows={2}
                className="mt-1 text-sm"
              />
            </div>

            {/* Rule snapshot */}
            {ruleSnapshot && (
              <div className="p-2.5 rounded-lg bg-accent/5 border border-accent/15 text-[11px]">
                <div>规则版本：{ruleSnapshot.rules_version}</div>
                <div>线段引擎：{ruleSnapshot.segment_engine}</div>
              </div>
            )}

            {/* Circuit breaker */}
            <div className="p-2.5 rounded-lg bg-white/[0.02] border border-border-subtle">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-[11px]">连续不利 · 自检计数</span>
                <span className="text-text-muted">当前</span>
                <span className="font-extrabold text-warning">{consecutiveLosses}</span>
                <span className="text-text-muted">次</span>
                <label className="flex items-center gap-1 ml-auto">
                  <span className="text-text-muted text-[11px]">熔断阈值</span>
                  <Input type="number" min={1} aria-label="连续不利熔断阈值（次数）" value={String(threshold)}
                    onChange={(e) => setThreshold(Number(e.target.value) || 5)}
                    className="w-16 text-center text-sm" />
                </label>
              </div>
              <div className="flex gap-2 mt-2">
                <Button size="sm" variant="light" onPress={incrementLoss}>+1 不利</Button>
                <Button size="sm" variant="light" onPress={resetLosses}>计数清零</Button>
              </div>
              {thresholdReached && (
                <div className="mt-2 p-2 rounded bg-danger/10 border border-danger/30 text-danger font-bold text-[11px]">
                  已连续记录达到阈值：建议<b>停机复盘</b>，勿试图「一笔扳回」。
                </div>
              )}
            </div>
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
