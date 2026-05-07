import { Button, ButtonGroup, Checkbox } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";

const PRESETS = [
  { key: "watch", label: "看盘", title: "看盘常用组合：本级结构 + BOLL / RSI，分型与背驰默认关闭，减少噪声。" },
  { key: "review", label: "复盘", title: "复盘核对：打开分型与背驰等辅助标注，图上信息更密。" },
  { key: "minimal", label: "极简", title: "极简：只保留最关键的走势线与买卖点参考。" },
];

export function LayerPresets() {
  const activePreset = useSettingsStore((s) => s.activePreset);
  const applyPreset = useSettingsStore((s) => s.applyPreset);
  const compactSubplots = useSettingsStore((s) => s.compactSubplots);
  const toggleCompactSubplots = useSettingsStore((s) => s.toggleCompactSubplots);
  const toggleCompactToolbar = useSettingsStore((s) => s.toggleCompactToolbar);

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
      <Checkbox
        aria-label="紧凑副图"
        isSelected={compactSubplots}
        onChange={() => toggleCompactSubplots()}
      >
        <span className="text-[10px]">紧凑副图</span>
      </Checkbox>
      <div className="flex-1" />
      <Button size="sm" variant="ghost" className="text-[10px]" onPress={toggleCompactToolbar}>
        收起
      </Button>
    </div>
  );
}
