import { Button, ButtonGroup } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";

const PRESETS = [
  { key: "watch", label: "看盘", title: "看盘常用组合：本级结构 + BOLL / RSI，分型与背驰默认关闭，减少噪声。" },
  { key: "review", label: "复盘", title: "复盘核对：打开分型与背驰等辅助标注，图上信息更密。" },
  { key: "minimal", label: "极简", title: "极简：只保留最关键的走势线与买卖点参考。" },
];

export function LayerPresets() {
  const activePreset = useSettingsStore((s) => s.activePreset);
  const applyPreset = useSettingsStore((s) => s.applyPreset);

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 border-t border-border-subtle">
      <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">图层预设</span>
      <ButtonGroup size="sm" variant="outline">
        {PRESETS.map((p) => (
          <Button
            key={p.key}
            className={activePreset === p.key ? "bg-accent/15 text-accent border-accent/40" : ""}
            onPress={() => applyPreset(p.key)}
          >
            {p.label}
          </Button>
        ))}
      </ButtonGroup>
      <span className="text-[10px] text-text-muted">一键勾选后可逐项微调；鼠标悬停查看说明。</span>
    </div>
  );
}
