import { escHtml } from "./utils.js";

const LS_LOSSES = "chanlan_consecutive_losses";
const LS_THRESH = "chanlan_circuit_loss_threshold";
const LS_HYPOTHESIS = "chanlan_hypothesis_notes";

export function updateDisciplineRuleSnap(result) {
  const el = document.getElementById("disciplineRuleSnap");
  if (!el) return;
  if (!result || !result.rules_version) {
    el.innerHTML = `<span class="muted">请先完成一次「分析」，以便锁定本次视图对应的规则快照。</span>`;
    return;
  }
  el.innerHTML = `
    <div><strong>规则快照（谈绩效前请先锁死）</strong></div>
    <div style="margin-top:6px;">rules_version：<code>${escHtml(String(result.rules_version))}</code></div>
    <div>segment_engine：<code>${escHtml(String(result.segment_engine || ""))}</code></div>
    <div style="margin-top:6px;font-size:10px;opacity:.85;">合并 K / 线段引擎一变，曲线就会变；样本外对比时请固定上述版本再解读回测。</div>
  `;
}

export function clearDisciplineRuleSnap() {
  const el = document.getElementById("disciplineRuleSnap");
  if (el)
    el.innerHTML = `<span class="muted">当前无有效分析结果；请先「分析」或检查报错。</span>`;
}

function readLossCount() {
  const n = parseInt(localStorage.getItem(LS_LOSSES) || "0", 10);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

function writeLossCount(n) {
  localStorage.setItem(LS_LOSSES, String(Math.max(0, n)));
}

function refreshCircuitUi() {
  const countEl = document.getElementById("circuitLossCount");
  const warn = document.getElementById("circuitBreakerWarn");
  const thInput = document.getElementById("circuitLossThreshold");
  if (!countEl) return;
  const n = readLossCount();
  countEl.textContent = String(n);
  const thRaw = thInput ? parseInt(thInput.value || "5", 10) : 5;
  const th = Number.isFinite(thRaw) && thRaw > 0 ? thRaw : 5;
  if (warn) warn.hidden = !(n >= th);
}

export function initDisciplineUi() {
  document.querySelectorAll(".risk-preset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const frac = btn.getAttribute("data-frac");
      const inp = document.getElementById("riskFrac");
      if (inp && frac != null) inp.value = frac;
    });
  });

  const thInput = document.getElementById("circuitLossThreshold");
  if (thInput) {
    try {
      const saved = localStorage.getItem(LS_THRESH);
      if (saved != null) thInput.value = saved;
    } catch {
      /* ignore */
    }
    thInput.addEventListener("change", () => {
      try {
        localStorage.setItem(LS_THRESH, thInput.value || "5");
      } catch {
        /* ignore */
      }
      refreshCircuitUi();
    });
  }

  document.getElementById("circuitLossInc")?.addEventListener("click", () => {
    writeLossCount(readLossCount() + 1);
    refreshCircuitUi();
  });
  document.getElementById("circuitLossReset")?.addEventListener("click", () => {
    writeLossCount(0);
    refreshCircuitUi();
  });

  const hyp = document.getElementById("disciplineHypothesisNotes");
  if (hyp) {
    try {
      hyp.value = localStorage.getItem(LS_HYPOTHESIS) || "";
    } catch {
      /* ignore */
    }
    hyp.addEventListener(
      "change",
      () => {
        try {
          localStorage.setItem(LS_HYPOTHESIS, hyp.value || "");
        } catch {
          /* ignore */
        }
      },
      false
    );
  }

  refreshCircuitUi();
}
