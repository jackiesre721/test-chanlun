export function AppFooter() {
  return (
    <footer className="compliance-footer">
      <svg className="compliance-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M8 1L14.5 5v6L8 15 1.5 11V5L8 1z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
        <path d="M8 5.5v3M8 11v.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
      </svg>
      <span>
        <strong>风险提示</strong> — 仅供缠论结构与 AI 摘要技术展示，不构成投资建议，非下单指令。交易风险自负。
      </span>
    </footer>
  );
}
