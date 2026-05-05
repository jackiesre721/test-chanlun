import { useSettingsStore } from "@/stores/settings-store";
import { ChartPane } from "@/components/chart/chart-pane";
import { Sidebar } from "@/components/sidebar/sidebar";

export function MainLayout() {
  const hideSidebar = useSettingsStore((s) => s.hideSidebar);

  /* 必须用 flex（或单列 grid）：仅去掉 grid 时 ChartPane 的 flex-1 不生效，主图会塌成零高 */
  return (
    <div className="flex flex-1 min-h-0 min-w-0 flex-row">
      <ChartPane />
      {!hideSidebar && (
        <aside className="flex w-[min(36vw,420px)] min-w-[280px] max-w-[36vw] shrink-0 flex-col overflow-hidden">
          <Sidebar />
        </aside>
      )}
    </div>
  );
}
