import { Spinner } from "@heroui/react";
import { useAnalysisStore } from "@/stores/analysis-store";

export function LoadingOverlay() {
  const analyzing = useAnalysisStore((s) => s.analyzing);
  if (!analyzing) return null;

  return (
    <div className="fixed inset-0 bg-bg-deep/60 flex items-center justify-center z-50 pointer-events-none">
      <div className="flex flex-col items-center gap-3">
        <Spinner size="lg" color="primary" />
        <span className="text-sm text-text-muted">分析中…</span>
      </div>
    </div>
  );
}
