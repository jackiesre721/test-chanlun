export function fmtOpenTime(ms: number | null | undefined): string {
  if (ms == null) return "—";
  try {
    return new Date(Number(ms)).toLocaleString("zh-CN", {
      hour12: false,
      timeZone: "Asia/Shanghai",
    });
  } catch {
    return String(ms);
  }
}

export function structureKindLabel(sk: string): string {
  return sk === "trend" ? "趋势背驰" : "盘整类背驰";
}

export function recursionBadgeClass(comp: string | null | undefined): string {
  if (!comp) return "adv-badge neutral";
  if (comp === "cross_level_divergent") return "adv-badge divergent";
  if (comp === "insufficient_higher_data") return "adv-badge warn";
  if (comp.startsWith("aligned")) return "adv-badge aligned";
  return "adv-badge neutral";
}
