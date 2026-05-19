import { Select, ListBox, Button } from "@heroui/react";
import { useSettingsStore } from "@/stores/settings-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { useEffect } from "react";
import { getSymbols } from "@/lib/api";
import { HIGHER_INTERVAL, INTERVAL_LABEL } from "@/constants/level-maps";

const INTERVAL_OPTIONS = [
  { value: "1", label: "1 分钟" },
  { value: "5", label: "5 分钟" },
  { value: "15", label: "15 分钟" },
  { value: "30", label: "30 分钟" },
  { value: "60", label: "1 小时" },
  { value: "240", label: "4 小时" },
  { value: "1440", label: "1 天" },
  { value: "10080", label: "1 周" },
  { value: "43200", label: "1 月" },
];

export function ToolbarPrimary() {
  const { symbol, interval, dynamicSymbols, compactToolbar, hideSidebar,
    setSymbol, setInterval, setDynamicSymbols, toggleCompactToolbar, toggleHideSidebar, setViewMode } = useSettingsStore();
  const { analyze, analyzing } = useAnalysisStore();

  const allSymbols = dynamicSymbols.length > 0 ? dynamicSymbols : ["BTCUSDT", "ETHUSDT"];

  useEffect(() => {
    getSymbols().then((syms) => {
      if (syms.length) setDynamicSymbols(syms.map((s) => s.symbol));
    });
  }, []);

  const handleAnalyze = () => analyze(symbol, interval);

  return (
    <div className="toolbar-bar flex items-center gap-3 px-4 py-2.5 flex-wrap">
      {/* Brand */}
      <div className="flex items-center gap-2.5 mr-3">
        <svg className="brand-mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 7c3 0 3 10 6 10s3-10 6-10 3 10 6 10" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
          <path d="M4 17c3 0 3-10 6-10s3 10 6 10 3-10 6-10" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" opacity="0.3"/>
        </svg>
        <div className="flex flex-col leading-none">
          <span className="text-[15px] font-semibold tracking-tight text-text-primary">Chanlan</span>
          <span className="text-[9px] font-medium tracking-widest uppercase text-text-muted mt-px">缠论 · 结构终端</span>
        </div>
      </div>

      {/* Symbol select */}
      <Select
        selectedKey={symbol}
        onSelectionChange={(key) => key && setSymbol(key as string)}
        className="w-36"
        aria-label="品种"
      >
        <Select.Trigger>
          <Select.Value />
        </Select.Trigger>
        <Select.Popover>
          <ListBox>
            {allSymbols.map((s) => (
              <ListBox.Item key={s} id={s}>{s}</ListBox.Item>
            ))}
          </ListBox>
        </Select.Popover>
      </Select>

      {/* Interval select */}
      <Select
        selectedKey={interval}
        onSelectionChange={(key) => key && setInterval(key as string)}
        className="w-56"
        aria-label="周期"
      >
        <Select.Trigger>
          <Select.Value />
        </Select.Trigger>
        <Select.Popover>
          <ListBox>
            {INTERVAL_OPTIONS.map((o) => (
              <ListBox.Item key={o.value} id={o.value}>{o.label}</ListBox.Item>
            ))}
          </ListBox>
        </Select.Popover>
      </Select>
      {HIGHER_INTERVAL[interval] && (
        <span className="text-[10px] text-text-muted tracking-wider">
          上级 → {INTERVAL_LABEL[HIGHER_INTERVAL[interval]] || HIGHER_INTERVAL[interval]}
        </span>
      )}

      {/* Analyze button */}
      <Button
        variant="primary"
        size="sm"
        onPress={handleAnalyze}
        isDisabled={analyzing}
        className="font-bold"
      >
        {analyzing ? "分析中…" : "分析"}
      </Button>

      {/* Layout toggles */}
      <div className="flex items-center gap-2">
        <Button size="sm" variant="ghost" onClick={() => setViewMode("trading")}>
          实盘
        </Button>
        <Button size="sm" variant="ghost" onPress={toggleHideSidebar}>
          {hideSidebar ? "显示侧栏" : "隐藏侧栏"}
        </Button>
        {compactToolbar && (
          <Button size="sm" variant="ghost" onPress={toggleCompactToolbar}>
            展开控件
          </Button>
        )}
      </div>

      <div className="flex-1" />

      {/* Status */}
      <div className="hidden lg:flex items-center gap-2 text-[10px] font-mono tracking-wider text-text-muted uppercase">
        <span className="status-dot"></span>
        严格结构 · 无证据不出点
      </div>
    </div>
  );
}
