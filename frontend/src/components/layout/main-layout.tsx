import { useEffect } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { ChartPane } from "@/components/chart/chart-pane";
import { Sidebar } from "@/components/sidebar/sidebar";

export function MainLayout() {
  const hideSidebar = useSettingsStore((s) => s.hideSidebar);
  const toggleHideSidebar = useSettingsStore((s) => s.toggleHideSidebar);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        toggleHideSidebar();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggleHideSidebar]);

  return (
    <div className="flex flex-1 min-h-0 min-w-0 flex-row">
      <ChartPane />
      {!hideSidebar && (
        <aside className="flex w-[min(30vw,380px)] min-w-[280px] max-w-[30vw] shrink-0 flex-col overflow-hidden">
          <Sidebar />
        </aside>
      )}
    </div>
  );
}
