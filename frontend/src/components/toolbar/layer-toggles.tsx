import { useState } from "react";
import { Checkbox, Tooltip } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import type { LayerKey } from "@/constants/layer-presets";

const LAYER_GROUPS = [
  {
    label: "核心",
    items: [
      { key: "showBis" as LayerKey, label: "本级笔", tip: "分型确认之后的定向折线，是本级别的笔。" },
      { key: "showActiveBi" as LayerKey, label: "未完成笔", tip: "最后一笔尚未被反向分型封闭；虚线表示未完成。" },
      { key: "showBiPause" as LayerKey, label: "笔停顿", tip: "笔端点附近的停顿提示，便于观察换挡区域。" },
      { key: "showSegments" as LayerKey, label: "线段", tip: "由若干笔构成的更大级别折线结构。" },
      { key: "showFractals" as LayerKey, label: "分型", tip: "三根 K 线构成的局部顶/底分型。" },
      { key: "showSignals" as LayerKey, label: "买卖点", tip: "规则满足时的买卖点标注；仅供语境披露。" },
      { key: "showDivergences" as LayerKey, label: "背驰点", tip: "走势与力度的背离标记；提示衰竭语境。" },
      { key: "showZhongshu" as LayerKey, label: "笔中枢带", tip: "三笔重叠的盘整区间 [ZD,ZG]，本级震荡箱体。" },
      { key: "showZhongshuSeg" as LayerKey, label: "线段中枢带", tip: "线段级中枢区间，跨度更大。" },
    ],
  },
  {
    label: "辅助",
    items: [
      { key: "showBoll" as LayerKey, label: "BOLL", tip: "布林带：上轨/中轨/下轨刻画价格波动通道。" },
      { key: "showRsi" as LayerKey, label: "RSI", tip: "RSI(14)：相对强弱指标，显示在下方副图。" },
      { key: "showFakeBi" as LayerKey, label: "FakeBI", tip: "虚拟笔线段，用于几何对齐或补缺。" },
      { key: "showBisLv2" as LayerKey, label: "上级笔", tip: "更大级别映射到当前图表上的笔走向。" },
      { key: "showZhongshuLv2" as LayerKey, label: "上级中枢", tip: "更大级别的中枢在主周期上的投影带。" },
    ],
  },
];

export function LayerToggles() {
  const [open, setOpen] = useState(false);
  const layers = useSettingsStore((s) => s.layers);
  const toggleLayer = useSettingsStore((s) => s.toggleLayer);

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
          {LAYER_GROUPS.map((group) => (
            <div key={group.label} className="flex flex-col gap-1.5">
              <span className="text-[10px] font-bold text-text-muted/70 uppercase tracking-wider">{group.label}</span>
              {group.items.map((item) => (
                <Tooltip key={item.key} content={item.tip} size="sm" placement="right">
                  <div>
                    <Checkbox
                      size="sm"
                      aria-label={item.label}
                      isSelected={layers[item.key]}
                      onChange={() => toggleLayer(item.key)}
                    >
                      {item.label}
                    </Checkbox>
                  </div>
                </Tooltip>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
