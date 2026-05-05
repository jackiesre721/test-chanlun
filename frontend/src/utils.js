export function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function fmtOpenTime(ms) {
  if (ms == null || ms === undefined) return "—";
  try {
    return new Date(Number(ms)).toLocaleString("zh-CN", {
      hour12: false,
      timeZone: "Asia/Shanghai"
    });
  } catch (e) {
    return String(ms);
  }
}

export function structureKindLabel(sk) {
  return sk === "trend" ? "趋势背驰" : "盘整类背驰";
}

export function recursionBadgeClass(comp) {
  if (!comp) return "adv-badge neutral";
  if (comp === "cross_level_divergent") return "adv-badge divergent";
  if (comp === "insufficient_higher_data") return "adv-badge warn";
  if (String(comp).startsWith("aligned")) return "adv-badge aligned";
  return "adv-badge neutral";
}
