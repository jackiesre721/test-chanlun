/** DOM helpers kept minimal to avoid import cycles between signals ↔ sidebar. */

export function setRiskEntryPrice(price) {
  const entry = document.getElementById("riskEntry");
  if (!entry || price == null) return;
  const n = Number(price);
  if (!Number.isFinite(n)) return;
  entry.value = String(n);
}
