import { useState } from "react";
import { Checkbox, Tooltip } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { levelLabel, higherLabel } from "@/constants/level-maps";
import type { LayerKey } from "@/constants/layer-presets";

interface LayerItem {
  key: LayerKey;
  label: string;
  tip: string;
}

function buildLayerGroups(interval: string): { label: string; items: LayerItem[] }[] {
  const lv = levelLabel(interval);
  const hi = higherLabel(interval);
  return [
    {
      label: "核心",
      items: [
        { key: "showBis", label: `${lv}笔`, tip: `分型确认之后的定向折线，${lv}级别的笔。` },
        { key: "showActiveBi", label: `${lv}未完成笔`, tip: "最后一笔尚未被反向分型封闭；虚线表示未完成。" },
        { key: "showSegments", label: `${hi}笔`, tip: `由若干笔构成的更大级别折线结构（≈${hi}级别笔）。` },
        { key: "showFractals", label: "分型", tip: "三根 K 线构成的局部顶/底分型。" },
        { key: "showSignals", label: "买卖点", tip: "规则满足时的买卖点标注；标注对应级别和类型。" },
        { key: "showDivergences", label: "背驰点", tip: "走势与力度的背离标记；提示衰竭语境。" },
        { key: "showZhongshu", label: `${lv}中枢`, tip: `三笔重叠的盘整区间 [ZD,ZG]，${lv}级别震荡箱体。` },
        { key: "showZhongshuSeg", label: `${hi}中枢`, tip: `${hi}级别中枢区间，跨度更大的震荡箱体。` },
      ],
    },
    {
      label: "辅助",
      items: [
        { key: "showBoll", label: "BOLL", tip: "布林带：上轨/中轨/下轨刻画价格波动通道。" },
        { key: "showRsi", label: "RSI", tip: "RSI(14)：相对强弱指标，显示在下方副图。" },
        { key: "showFakeBi", label: "FakeBI", tip: "虚拟笔线段，用于几何对齐或补缺。" },
      ],
    },
  ];
}

export function LayerToggles() {
  const [open, setOpen] = useState(false);
  const layers = useSettingsStore((s) => s.layers);
  const toggleLayer = useSettingsStore((s) => s.toggleLayer);
  const interval = useSettingsStore((s) => s.interval);
  const groups = buildLayerGroups(interval);

  return (
    <div className="border-t border-border-subtle bg-black/20">
      <button
        className="w-full px-4 py-2 text-[11px] font-semibold text-text-muted uppercase tracking-wider text-left cursor-pointer hover:text-text-primary transition-colors"
        onClick={() => setOpen(!open)}
      >
        {open ? "▾" : "▸"} 图层开关（点击展开）
      </button>
      {open && (
        <div className="px-4 pb-3 flex gap-8 flex-wrap">
          {groups.map((group) => (
            <div key={group.label} className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold text-text-muted/70 uppercase tracking-wider">{group.label}</span>
              {group.items.map((item) => (
                <Tooltip key={item.key}>
                  <Tooltip.Trigger>
                    <div>
                      <Checkbox
                        className="text-sm"
                        aria-label={item.label}
                        isSelected={layers[item.key]}
                        onChange={() => toggleLayer(item.key)}
                      >
                        {item.label}
                      </Checkbox>
                    </div>
                  </Tooltip.Trigger>
                  <Tooltip.Content>{item.tip}</Tooltip.Content>
                </Tooltip>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
