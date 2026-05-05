import { TREND_CODE_LABEL, RECURSION_COMP_LABEL } from "./constants.js";
import { escHtml, fmtOpenTime, recursionBadgeClass } from "./utils.js";

export function pickAdvancedContext(root) {
  if (!root || typeof root !== "object") return null;
  const from = o => {
    if (!o || typeof o !== "object") return null;
    const v = o.advanced_context ?? o.advancedContext ?? o.chanAdvancedContext;
    return v != null && typeof v === "object" ? v : null;
  };
  let v = from(root);
  if (v) return v;
  for (const k of ["data", "result", "payload", "body"]) {
    v = from(root[k]);
    if (v) return v;
  }
  return null;
}

function clientSegmentTrendRunsPlaceholder(segments, segmentEngine) {
  const segs = segments || [];
  const runs = [];
  let start = 0;
  for (let i = 1; i <= segs.length; i++) {
    if (i === segs.length || segs[i].direction !== segs[start].direction) {
      const block = segs.slice(start, i);
      let rh = -Infinity;
      let rl = Infinity;
      for (const s of block) {
        rh = Math.max(rh, s.start_price, s.end_price);
        rl = Math.min(rl, s.start_price, s.end_price);
      }
      runs.push({
        start_seg_index: start,
        end_seg_index: i - 1,
        direction: segs[start].direction,
        segment_count: i - start,
        run_high: rh,
        run_low: rl,
        level: "segment",
        merge_rule: "contiguous_same_direction_segments_v1;client-fallback",
        schema_version: "chanlan-client-fallback-1",
        trend_type_code: "neutral_single_segment",
        trend_type_note_zh:
          "后端未返回 advanced_context：此处仅同向线段合并占位，无线段中枢走势类型与跨级递归。",
        trend_rule_table_id: "client-fallback-v1",
        segment_engine: segmentEngine || "legacy",
      });
      start = i;
    }
  }
  return runs;
}

export function ensureAdvancedContextMerged(result) {
  if (!result || typeof result !== "object") return;
  if (pickAdvancedContext(result) != null) return;
  if (result.advanced_context != null && typeof result.advanced_context === "object") return;
  const zh = result.zhongshus || [];
  const biPivots = zh.filter(p => p.level === "bi");
  let znMid = null;
  let znNote = null;
  if (biPivots.length) {
    const last = biPivots[biPivots.length - 1];
    znMid = (Number(last.zg) + Number(last.zd)) / 2;
    znNote =
      "前端按最后一座笔中枢推算 Zn=(ZG+ZD)/2，仅供占位；完整进阶请升级含 advanced_context 的 API。";
  }
  const runs = clientSegmentTrendRunsPlaceholder(result.segments, result.segment_engine);
  result.advanced_context = {
    higher_interval: null,
    nested_interval: null,
    abc_decomposition: null,
    segment_trend_runs: runs,
    trend_recursion: {
      composite: "insufficient_higher_data",
      note_zh:
        "当前响应缺少 advanced_context（以及你这份 JSON 里也没有 lines_form、segment_engine，与仓库最新 AnalyzeResponse 不一致）。以下为浏览器有限补办；部署本仓库后端后应出现完整字段。",
      higher_lines_form_primary: result.lines_form ? result.lines_form.primary : null,
      base_last_run_trend_code: runs.length ? runs[runs.length - 1].trend_type_code : null,
      rule_table_version: "client-fallback-v1",
    },
    zn_last_bi_mid: znMid,
    zn_note_zh: znNote,
    bi_pause_hint: null,
    gap_last_bi: null,
    __clientAdvancedFallback: true,
  };
}

export function renderAdvancedPanel(result) {
  const el = document.getElementById("advancedPanel");
  if (!el) return;
  const adv = pickAdvancedContext(result) ?? result.advanced_context ?? result.advancedContext;
  if (adv == null || typeof adv !== "object") {
    const keys = result && typeof result === "object" ? Object.keys(result).slice(0, 30).join(", ") : "";
    el.innerHTML = `<span class="warn">仍未解析到 advanced_context。当前结果顶层键：${escHtml(keys || "—")}。<br/><br/>请检查：① 后端已部署且含该字段；② 网关是否在 <code>data</code>/<code>result</code> 内嵌套（本页已尝试解包）；③ 若 API 不在根路径，设置页内 <code>&lt;meta name="chanlan-api-prefix" content="/你的前缀"/&gt;</code>。</span>`;
    return;
  }
  const parts = [];
  if (adv.__clientAdvancedFallback) {
    parts.push(
      `<div style="margin:0 0 12px;padding:10px 12px;border-radius:10px;background:rgba(255,183,77,.14);border:1px solid rgba(255,183,77,.35);font-size:11px;line-height:1.55;color:#ffe6c8;"><b>前端补办模式</b>：当前 JSON 无服务端 <code>advanced_context</code>（且你这份响应也缺少 <code>lines_form</code>、<code>segment_engine</code>，与仓库最新 <code>AnalyzeResponse</code> 不一致）。下表为浏览器用 <code>segments</code>/<code>zhongshus</code> 做的<strong>占位</strong>，不等价于引擎；请 <strong>git pull 并重启</strong> 本仓库 API。</div>`
    );
  }
  parts.push(
    `<div class="adv-meta">字段与 <code>advanced_context</code> 一一对应。上级周期：<b>${adv.higher_interval || "—"}</b>｜本页规则版本：<b>${result.rules_version || "—"}</b>｜线段引擎：<b>${result.segment_engine || adv.segment_trend_runs?.[0]?.segment_engine || "—"}</b></div>`
  );
  const zsAll = result.zhongshus || [];
  if (zsAll.length) {
    const symN = zsAll.filter(p => p.symmetry_zs === true).length;
    parts.push(
      `<div class="adv-note" style="margin-bottom:10px">中枢 <code>symmetry_zs</code>：<b>${symN}</b> / ${zsAll.length}；虚拟笔 <code>fake_bis</code>：<b>${(result.fake_bis || []).length}</b> 段</div>`
    );
  }

  if (adv.nested_interval && adv.nested_interval.slices && adv.nested_interval.slices.length) {
    const ni = adv.nested_interval;
    parts.push(`<div class="adv-h3">区间套 nested_interval</div>`);
    parts.push(`<div class="adv-note">${escHtml(ni.summary_zh || "")}</div>`);
    parts.push(
      `<div class="adv-note">alignment_rule_id：<code>${escHtml(ni.alignment_rule_id || "")}</code>｜time_axis：${escHtml(ni.time_axis || "")}</div>`
    );
    parts.push(
      '<div class="adv-scroll"><table class="adv-table"><thead><tr><th>上级笔#</th><th>向</th><th>本级K index</th><th>本级 open_time</th><th>上级 bar#</th><th>上级 open_time</th><th>子笔数</th><th>lines_form</th><th>笔枢数</th></tr></thead><tbody>'
    );
    ni.slices.forEach(s => {
      parts.push(
        `<tr><td>${s.higher_stroke_index}</td><td>${s.higher_direction === "UP" ? "上" : "下"}</td><td>${s.candle_index_lo}–${s.candle_index_hi}</td><td>${fmtOpenTime(s.base_open_time_lo)}<br/>${fmtOpenTime(s.base_open_time_hi)}</td><td>${s.higher_bar_index_lo != null ? s.higher_bar_index_lo + "–" + s.higher_bar_index_hi : "—"}</td><td>${fmtOpenTime(s.higher_open_time_lo)}<br/>${fmtOpenTime(s.higher_open_time_hi)}</td><td>${s.sub_stroke_count}</td><td><b>${escHtml(s.lines_form_primary)}</b><div class="adv-note">${escHtml(s.lines_form_detail_zh || "")}</div></td><td>${s.bi_pivot_count}</td></tr>`
      );
    });
    parts.push("</tbody></table></div>");
    parts.push('<div class="adv-note" style="margin-top:6px">');
    ni.slices.forEach(s => {
      parts.push(`<div>· ${escHtml(s.hint_zh || "")}</div>`);
    });
    parts.push("</div>");
  } else {
    parts.push(`<div class="adv-h3">区间套 nested_interval</div>`);
    parts.push(`<div class="adv-note">无上周期映射或 slices 为空。</div>`);
  }

  if (adv.abc_decomposition && adv.abc_decomposition.parts && adv.abc_decomposition.parts.length) {
    parts.push(`<div class="adv-h3">a+A+b+B+c（abc_decomposition）</div>`);
    parts.push(
      '<div class="adv-scroll" style="max-height:120px"><table class="adv-table"><thead><tr><th>片段</th><th>笔 from–to</th></tr></thead><tbody>'
    );
    adv.abc_decomposition.parts.forEach(p => {
      parts.push(`<tr><td><b>${escHtml(p.label)}</b></td><td>${p.from_bi} – ${p.to_bi}</td></tr>`);
    });
    parts.push("</tbody></table></div>");
    if (adv.abc_decomposition.note_zh) {
      parts.push(`<div class="adv-note">${escHtml(adv.abc_decomposition.note_zh)}</div>`);
    }
  } else {
    parts.push(`<div class="adv-h3">a+A+b+B+c</div><div class="adv-note">未形成双中枢堆叠粗分（abc_decomposition 为空）。</div>`);
  }

  if (adv.segment_trend_runs && adv.segment_trend_runs.length) {
    const r0 = adv.segment_trend_runs[0];
    parts.push(`<div class="adv-h3">线段走势段 segment_trend_runs（${adv.segment_trend_runs.length}）</div>`);
    parts.push(
      `<div class="adv-note">走势规则表：<code>${escHtml(r0.trend_rule_table_id || "")}</code>｜schema：<code>${escHtml(r0.schema_version || "")}</code></div>`
    );
    parts.push(
      '<div class="adv-scroll" style="max-height:220px"><table class="adv-table"><thead><tr><th>段序</th><th>向</th><th>根数</th><th>价幅 low–high</th><th>trend_type_code</th><th>说明</th><th>merge_rule</th><th>engine</th></tr></thead><tbody>'
    );
    adv.segment_trend_runs.forEach(r => {
      const lbl = TREND_CODE_LABEL[r.trend_type_code] || r.trend_type_code;
      parts.push(
        `<tr><td>${r.start_seg_index}–${r.end_seg_index}</td><td>${r.direction === "UP" ? "上" : "下"}</td><td>${r.segment_count}</td><td>${Number(r.run_low).toFixed(4)} – ${Number(r.run_high).toFixed(4)}</td><td><b>${escHtml(r.trend_type_code)}</b><div class="adv-note">${escHtml(lbl)}</div></td><td class="adv-note">${escHtml(r.trend_type_note_zh || "")}</td><td class="adv-note" style="max-width:120px;word-break:break-all;">${escHtml(r.merge_rule || "")}</td><td>${escHtml(r.segment_engine || "")}</td></tr>`
      );
    });
    parts.push("</tbody></table></div>");
  } else {
    parts.push(`<div class="adv-h3">线段走势段</div><div class="adv-note">无线段或 runs 为空。</div>`);
  }

  if (adv.trend_recursion) {
    const tr = adv.trend_recursion;
    const compLabel = RECURSION_COMP_LABEL[tr.composite] || tr.composite;
    parts.push(`<div class="adv-h3">走势递归 trend_recursion</div>`);
    parts.push(
      `<div><span class="${recursionBadgeClass(tr.composite)}">${escHtml(compLabel)}</span> <span class="adv-note">rule_table_version: <code>${escHtml(tr.rule_table_version || "")}</code></span></div>`
    );
    if (tr.note_zh) parts.push(`<div class="adv-note" style="margin-top:8px">${escHtml(tr.note_zh)}</div>`);
    parts.push(
      `<div class="adv-note">上级末片 lines_form：<b>${escHtml(tr.higher_lines_form_primary || "—")}</b>｜本级末段走势码：<b>${escHtml(tr.base_last_run_trend_code || "—")}</b></div>`
    );
  }

  if (adv.zn_last_bi_mid != null || adv.zn_note_zh) {
    parts.push(`<div class="adv-h3">Zn（笔中枢中轴）</div>`);
    parts.push(
      `<div class="adv-note">zn_last_bi_mid：<b>${adv.zn_last_bi_mid != null ? adv.zn_last_bi_mid : "—"}</b></div><div class="adv-note">${escHtml(adv.zn_note_zh || "")}</div>`
    );
  }

  if (adv.bi_pause_hint) {
    parts.push(`<div class="adv-h3">笔停顿 bi_pause_hint</div>`);
    parts.push(`<div style="color:#ffbf69;font-size:11px;">${escHtml(adv.bi_pause_hint)}</div>`);
  }

  if (adv.gap_last_bi) {
    const g = adv.gap_last_bi;
    parts.push(`<div class="adv-h3">缺口 gap_last_bi</div>`);
    parts.push(
      `<div class="adv-note">笔序号 #${g.stroke_bi_index}｜K index ${g.candle_lo}–${g.candle_hi}｜上跳缺口 <b>${g.up_gaps}</b>｜下跳缺口 <b>${g.down_gaps}</b></div>`
    );
  }

  el.innerHTML = parts.join("");
}
