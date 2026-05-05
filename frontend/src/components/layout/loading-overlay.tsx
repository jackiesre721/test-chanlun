import { useAnalysisStore } from "@/stores/analysis-store";

export function LoadingOverlay() {
  const analyzing = useAnalysisStore((s) => s.analyzing);
  if (!analyzing) return null;

  return (
    <div className="loading-overlay">
      <div className="flex flex-col items-center gap-4">
        <div className="loading-ring"></div>
        <span className="text-sm text-text-muted font-mono tracking-wider">分析中…</span>
      </div>
    </div>
  );
}
