import { useSettingsStore } from "@/stores/settings-store";
import { useAnalysisStore } from "@/stores/analysis-store";
import { ToolbarPrimary } from "./toolbar-primary";
import { LayerPresets } from "./layer-presets";
import { LayerToggles } from "./layer-toggles";

export function Toolbar() {
  const compact = useSettingsStore((s) => s.compactToolbar);
  const analyzing = useAnalysisStore((s) => s.analyzing);

  return (
    <div className={`bg-bg-toolbar border-b border-border-subtle ${analyzing ? "analyzing" : ""}`}>
      <ToolbarPrimary />
      {!compact && (
        <>
          <LayerPresets />
          <LayerToggles />
        </>
      )}
    </div>
  );
}
