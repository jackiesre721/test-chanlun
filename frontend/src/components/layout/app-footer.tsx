export function AppFooter() {
  return (
    <footer className="compliance-footer">
      <svg className="compliance-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M8 1L14.5 5v6L8 15 1.5 11V5L8 1z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
        <path d="M8 5.5v3M8 11v.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
      </svg>
      <div>
        <strong>风险提示</strong> — 本页仅供缠论结构与 AI 摘要的技术展示，不构成投资建议；任何买卖点与模型结论均非下单指令。
        盈利更应理解为<b>期望值与次数</b>，单笔风控与熔断优先于「看准一波」。交易风险与合规责任由您自行承担。
      </div>
    </footer>
  );
}
