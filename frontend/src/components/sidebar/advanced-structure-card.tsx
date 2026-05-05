import { Card, CardContent } from "@heroui/react";
import { Disclosure, DisclosureTrigger, DisclosureContent } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";
import type { AdvancedContext } from "@/types/analysis";

export function AdvancedStructureCard() {
  const lastResult = useAnalysisStore((s) => s.lastResult);
  const adv = lastResult?.advanced_context;

  return (
    <Disclosure>
      <Card className="bg-bg-card border border-border-subtle">
        <DisclosureTrigger>
          <div className="font-bold text-sm px-3 py-2 cursor-pointer hover:text-accent transition-colors flex items-center gap-2">
            进阶结构
            <span className="text-[11px] text-text-muted font-normal">（表格较长，默认折叠）</span>
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 text-xs text-text-muted">
            {!adv ? (
              <div>分析后展示区间套、跨级递归、走势类型等完整结构字段。</div>
            ) : (
              <div className="space-y-3">
                {adv.__clientAdvancedFallback && (
                  <div className="p-2 rounded bg-warning/10 border border-warning/30 text-warning text-[11px]">
                    注意：advanced_context 未从服务端返回，以下为客户端合成数据。
                  </div>
                )}
                {adv.higher_interval && <div>上级周期：{adv.higher_interval}</div>}
                {adv.rules_version && <div>规则版本：{adv.rules_version}</div>}
                {adv.segment_engine && <div>线段引擎：{adv.segment_engine}</div>}
                {adv.zhongshu_symmetry && (
                  <div>
                    <div className="font-bold mb-1">中枢对称性</div>
                    {Object.entries(adv.zhongshu_symmetry).map(([k, v]) => (
                      <div key={k}>{k}: {v}</div>
                    ))}
                  </div>
                )}
                {adv.fake_bi_count != null && <div>虚拟笔数量：{adv.fake_bi_count}</div>}
                {Array.isArray(adv.nested_interval) && adv.nested_interval.length > 0 && (
                  <div>
                    <div className="font-bold mb-1">区间套 ({adv.nested_interval.length} 条)</div>
                    <div className="max-h-40 overflow-auto">
                      <table className="w-full text-[10px]">
                        <thead><tr className="text-text-muted"><th className="text-left">笔序</th><th>方向</th><th>K范围</th></tr></thead>
                        <tbody>
                          {adv.nested_interval.slice(0, 20).map((row: any, i: number) => (
                            <tr key={i}><td>{row.bi_idx ?? i}</td><td>{row.direction || "—"}</td><td>{row.k_start ?? "?"}–{row.k_end ?? "?"}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {adv.lines_form && <div>走势形态：{adv.lines_form}</div>}
              </div>
            )}
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
