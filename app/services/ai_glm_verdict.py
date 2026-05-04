"""将分析结果交给智谱 GLM：全量/摘要语境 + 偏多偏空 + 参考价位（非投资建议）。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Literal, Optional

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.models import (
    ActionFocus,
    AiVerdictPriceHints,
    AiVerdictResponse,
    AnalyzeResponse,
    Candle,
    Direction,
    Signal,
    SignalSide,
)

VERDICT_ANALYSIS_DEFAULTS: dict[str, Any] = {
    "kline_data": [],
    "macd_data": [],
    "bollinger": [],
    "rsi14": [],
    "fractals": [],
    "bis": [],
    "active_bi": None,
    "segments": [],
    "divergences": [],
    "bis_lv2": [],
    "zhongshus": [],
    "zhongshus_lv2": [],
    "buy_signals": [],
    "sell_signals": [],
    "fake_bis": [],
    "kline_parent_refs": [],
    "warning": None,
    "advanced_context": {},
}

_BIAS = Literal["long", "short", "neutral"]

_SYSTEM_PROMPT = """你是缠论结构分析助手（不是证券投资顾问）。
用户 JSON 为程序根据 K 线推导的缠论数据（可能是全量字段或摘要）。
请结合中枢 ZD/ZG、买卖点价、未完成笔、背驰、走势形态、进阶结构等，用中文归纳语境，并给出**结构推演用的参考价位**（数字须与输入中价位同量级、可从 ZD/ZG/信号价/现价推演）。

叙事重心（非常重要）：
- 用户关心的是**后续行情结构与关键观察点**，不是「复述已经走出的 K 线故事」。
- summary_zh 必须以**接下来要盯什么**为主（区间突破/回抽、离开段是否延伸、背驰是否被确认等）；已出现的买卖点若需提及，只作**价位与结构锚点**，一句话内点到即可，不要以大段回放为主语。
- reasons_zh：2–8 条中，**至少一半**应写「若价格如何演化，结构含义可能如何变化」或「下一步确认/证伪需要什么条件」；至多 1 条用简短句说明「最近一条信号仅作锚点（时间/价位）」，避免通篇「历史上发生了什么」。
- 合规措辞集中到 price_note_zh（模型推演、自担风险、非投资建议）；正文少用「回放」「复盘」作为主叙事。

硬性要求：
- 只输出**一个** JSON 对象，禁止 markdown 代码围栏，禁止多余说明文字。
- 不得承诺收益；不得给出「必须买入/卖出」「满仓」等指令式语句（可在 price_note_zh 中声明为观察参考）。

JSON 键（必须全部给出；无数可用 null）：
- bias: 字符串，只能是 long、short、neutral
- confidence: 0 到 1 的小数
- summary_zh: 一句话 ≤90 字
- reasons_zh: 2 到 8 条字符串，每条应能对应输入中的字段或数值
- buy_focus_price: 数字或 null（做多一侧的**参考观察价**，非保证成交价）
- sell_focus_price: 数字或 null（做空一侧参考观察价）
- stop_loss_buy: 数字或 null（若给 buy_focus_price，可给跌破后多单结构失效侧的参考止损价，否则 null）
- stop_loss_sell: 数字或 null
- price_note_zh: 一句话，说明价位为模型推演、需自担风险"""


def pop_glm_request_options(body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回 (分析体, {api_key, model, full_context})。"""
    raw = dict(body)
    key = raw.pop("glm_api_key", None)
    model = raw.pop("glm_model", None)
    full = raw.pop("glm_full_context", True)
    if isinstance(full, str):
        full = full.strip().lower() in ("1", "true", "yes", "on")
    else:
        full = bool(full)
    opt = {
        "api_key": (str(key).strip() if key is not None else "") or None,
        "model": (str(model).strip() if model is not None else "") or None,
        "full_context": full,
    }
    return raw, opt


def merge_verdict_analysis_dict(body: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {**VERDICT_ANALYSIS_DEFAULTS, **body}
    ac = body.get("advanced_context")
    if isinstance(ac, dict) and ac:
        base_ac = VERDICT_ANALYSIS_DEFAULTS.get("advanced_context") or {}
        if isinstance(base_ac, dict):
            merged["advanced_context"] = {**base_ac, **ac}
        else:
            merged["advanced_context"] = ac
    return merged


def _compact_action_focus(af: ActionFocus) -> dict[str, Any]:
    def pack_slot(name: str, piv_slot) -> dict[str, Any]:
        if not piv_slot or piv_slot.relation == "none":
            return {name: {"relation": "none"}}
        pr = piv_slot.pivot
        base: dict[str, Any] = {name: {"relation": piv_slot.relation}}
        if pr:
            base[name]["pivot"] = {
                "lvl": pr.level,
                "zd": pr.zd,
                "zg": pr.zg,
            }
        return base

    out: dict[str, Any] = {
        "last_bar_index": af.last_bar_index,
        "current_price": af.current_price,
        **pack_slot("primary", af.primary_pivot),
        **pack_slot("higher", af.higher_pivot),
    }
    if af.active_bi:
        out["active_bi"] = {
            "dir": af.active_bi.direction.value,
            "from": af.active_bi.start_price,
            "to": af.active_bi.end_price,
        }
    if af.recent_divergence:
        out["recent_div"] = af.recent_divergence.model_dump(mode="json")
    if af.recent_signal:
        out["recent_sig"] = af.recent_signal.model_dump(mode="json")
    return out


def _sig_row(s: Signal, desc_max: int) -> dict[str, Any]:
    return {
        "side": s.side.value,
        "kind": s.kind,
        "time": s.time,
        "idx": s.idx,
        "price": round(s.price, 8),
        "strength": s.strength,
        "desc": (s.description or "")[:desc_max],
        "evidence": (s.evidence or "")[: min(400, desc_max * 2)],
    }


def _stroke_row_compact(b) -> dict[str, Any]:
    d = {
        "dir": b.direction.value,
        "from": round(b.start_price, 8),
        "to": round(b.end_price, 8),
        "i0": b.start_idx,
        "i1": b.end_idx,
    }
    extra = b.model_dump(mode="json", exclude={"direction", "start_price", "end_price", "start_idx", "end_idx"})
    for k in list(extra.keys()):
        if extra[k] is None:
            del extra[k]
    d.update({k: v for k, v in extra.items() if k not in d})
    return d


def _candle_row_mini(c: Candle) -> dict[str, Any]:
    return {
        "open_time": c.open_time,
        "t": c.time,
        "o": round(c.open, 8),
        "h": round(c.high, 8),
        "l": round(c.low, 8),
        "c": round(c.close, 8),
        "v": round(c.volume, 6),
    }


def _truncate_advanced_dump(r: AnalyzeResponse) -> dict[str, Any]:
    adv = r.advanced_context
    if not adv:
        return {}
    d = adv.model_dump(mode="json")
    ni = d.get("nested_interval")
    if isinstance(ni, dict):
        sl = ni.get("slices")
        if isinstance(sl, list) and len(sl) > 20:
            ni = {**ni, "slices": sl[:20], "_truncated_slices": len(sl) - 20}
            d["nested_interval"] = ni
    runs = d.get("segment_trend_runs")
    if isinstance(runs, list) and len(runs) > 35:
        d["segment_trend_runs"] = runs[:35]
        d["_truncated_segment_runs"] = len(runs) - 35
    return d


def compact_for_glm(r: AnalyzeResponse) -> dict[str, Any]:
    """轻量摘要（结构与近端信号）。"""
    adv = r.advanced_context
    adv_mini: dict[str, Any] = {}
    if adv:
        adv_mini["higher_interval"] = adv.higher_interval
        if adv.nested_interval:
            adv_mini["nested_summary_zh"] = (adv.nested_interval.summary_zh or "")[:500]
        if adv.trend_recursion:
            adv_mini["trend_recursion"] = {
                "composite": adv.trend_recursion.composite,
                "note_zh": (adv.trend_recursion.note_zh or "")[:500],
            }
        if adv.segment_trend_runs:
            last = adv.segment_trend_runs[-1]
            adv_mini["last_segment_run"] = {
                "code": last.trend_type_code,
                "note_zh": (last.trend_type_note_zh or "")[:280],
            }
        if adv.zn_note_zh or adv.zn_last_bi_mid is not None:
            adv_mini["zn"] = {"mid": adv.zn_last_bi_mid, "note_zh": (adv.zn_note_zh or "")[:280]}
        if adv.bi_pause_hint:
            adv_mini["bi_pause_hint"] = (adv.bi_pause_hint or "")[:280]

    def sig_tail(sigs: list[Signal], n: int, desc_max: int) -> list[dict[str, Any]]:
        return [_sig_row(s, desc_max) for s in sigs[-n:]]

    def div_tail(n: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for d in r.divergences[-n:]:
            rows.append(
                {
                    "lvl": d.level,
                    "dir": d.direction.value,
                    "sk": d.structure_kind,
                    "ratio": round(d.ratio, 6),
                    "pivot_idx": d.pivot_idx,
                    "note": (d.description or "")[:180],
                }
            )
        return rows

    rsi_last: Optional[float] = None
    if r.rsi14:
        for v in reversed(r.rsi14):
            if v is not None:
                rsi_last = round(float(v), 4)
                break

    return {
        "context_mode": "compact",
        "symbol": r.symbol,
        "interval": r.interval,
        "rules_version": r.rules_version,
        "segment_engine": r.segment_engine,
        "current_price": r.current_price,
        "lines_form": r.lines_form.model_dump(mode="json"),
        "td_summary": r.td_summary.model_dump(mode="json"),
        "action_focus": _compact_action_focus(r.action_focus),
        "bis_tail": [_stroke_row_compact(b) for b in r.bis[-8:]],
        "pivots_tail": [
            {
                "lvl": p.level,
                "zd": round(p.zd, 8),
                "zg": round(p.zg, 8),
                "bi": f"{p.start_bi}-{p.end_bi}",
            }
            for p in r.zhongshus[-4:]
        ],
        "buy_signals_tail": sig_tail(r.buy_signals, 6, 180),
        "sell_signals_tail": sig_tail(r.sell_signals, 6, 180),
        "divergences_tail": div_tail(4),
        "rsi14_last": rsi_last,
        "advanced": adv_mini,
        "warning": r.warning,
    }


def full_context_for_glm(r: AnalyzeResponse) -> dict[str, Any]:
    """在紧凑摘要之外，附带 K 线尾、全量笔/中枢/信号等（有长度上限）。"""
    base = deepcopy(compact_for_glm(r))
    base["context_mode"] = "full"
    n_k = min(160, len(r.kline_data))
    n_series = n_k
    if r.kline_data:
        base["kline_tail"] = [_candle_row_mini(c) for c in r.kline_data[-n_k:]]
    if r.macd_data:
        base["macd_tail"] = [m.model_dump(mode="json") for m in r.macd_data[-n_series:]]
    if r.bollinger:
        base["bollinger_tail"] = [b.model_dump(mode="json") for b in r.bollinger[-n_series:]]
    if r.rsi14:
        base["rsi14_tail"] = [x for x in r.rsi14[-n_series:]]
    base["fractals"] = [f.model_dump(mode="json") for f in r.fractals[-120:]]
    max_bi = 200
    base["bis"] = [_stroke_row_compact(b) for b in r.bis[-max_bi:]]
    if len(r.bis) > max_bi:
        base["_bis_total"] = len(r.bis)
        base["_bis_truncated_head"] = len(r.bis) - max_bi
    base["segments"] = [s.model_dump(mode="json") for s in r.segments[-120:]]
    base["zhongshus"] = [p.model_dump(mode="json") for p in r.zhongshus[-40:]]
    base["zhongshus_lv2"] = [p.model_dump(mode="json") for p in r.zhongshus_lv2[-25:]]
    base["bis_lv2"] = [_stroke_row_compact(b) for b in r.bis_lv2[-60:]]
    base["divergences"] = [d.model_dump(mode="json") for d in r.divergences[-35:]]
    base["buy_signals"] = [_sig_row(s, 400) for s in r.buy_signals[-40:]]
    base["sell_signals"] = [_sig_row(s, 400) for s in r.sell_signals[-40:]]
    if r.active_bi:
        base["active_bi_full"] = r.active_bi.model_dump(mode="json")
    base["fake_bis"] = [f.model_dump(mode="json") for f in r.fake_bis[-80:]]
    base["kline_parent_refs"] = [x.model_dump(mode="json") for x in r.kline_parent_refs[-200:]]
    base["advanced_context_full"] = _truncate_advanced_dump(r)
    return base


def build_glm_context(r: AnalyzeResponse, *, full_context: bool) -> dict[str, Any]:
    return full_context_for_glm(r) if full_context else compact_for_glm(r)


def _heuristic_price_hints(r: AnalyzeResponse, *, bias: _BIAS, latest: Optional[Signal]) -> AiVerdictPriceHints:
    note = "规则降级：参考价取自最近结构信号或中枢边界；不构成投资建议。"
    buy_p: Optional[float] = None
    sell_p: Optional[float] = None
    sl_buy: Optional[float] = None
    sl_sell: Optional[float] = None
    if latest:
        px = float(latest.price)
        if latest.side == SignalSide.BUY:
            buy_p = px
        else:
            sell_p = px

    zd_val: Optional[float] = None
    zg_val: Optional[float] = None
    if r.action_focus.primary_pivot.pivot:
        pr = r.action_focus.primary_pivot.pivot
        zd_val, zg_val = float(pr.zd), float(pr.zg)
    elif r.zhongshus:
        lp = r.zhongshus[-1]
        zd_val, zg_val = float(lp.zd), float(lp.zg)

    cp = float(r.current_price)
    if zd_val is not None and zg_val is not None:
        if bias == "long":
            if buy_p is None:
                buy_p = round(cp if zd_val <= cp <= zg_val else min(cp, zg_val), 8)
            sl_buy = round(zd_val, 8)
        elif bias == "short":
            if sell_p is None:
                sell_p = round(cp if zd_val <= cp <= zg_val else max(cp, zd_val), 8)
            sl_sell = round(zg_val, 8)
    return AiVerdictPriceHints(
        buy_focus_price=buy_p,
        sell_focus_price=sell_p,
        stop_loss_buy=sl_buy,
        stop_loss_sell=sl_sell,
        note_zh=note,
    )


def _forward_reason_lines(r: AnalyzeResponse, bias: _BIAS) -> list[str]:
    """偏「后续怎么走」的短句，减少通篇复述已发生信号。"""
    rel = r.action_focus.primary_pivot.relation if r.action_focus else "none"
    out: list[str] = []
    if rel == "inside":
        out.append(
            "后续可先跟踪：相对 ZG/ZD 的突破与回抽——上破后能否站稳、下破后能否收回，决定震荡是否升级成方向选择。"
        )
    elif rel == "above":
        out.append(
            "后续可先跟踪：回踩中枢上沿（ZG）一带能否守住；失守则更易回到区间内再择向（非下单指令）。"
        )
    elif rel == "below":
        out.append(
            "后续可先跟踪：反抽中枢下沿（ZD）一带能否站回；站不回则偏弱延伸观察延续（非下单指令）。"
        )
    else:
        out.append(
            "后续可先跟踪：现价与最近参考中枢 ZD/ZG 的相对位置变化，以及未完成笔何时被反向分型确认。"
        )
    if bias == "short":
        out.append(
            "偏空语境下：重点看上冲是否衰竭、离开段是否延伸或被背驰证据印证，再谈方向定型；避免仅凭已过卖点复读。"
        )
    elif bias == "long":
        out.append(
            "偏多语境下：重点看下探是否衰竭、离开段是否延伸或被背驰证据印证，再谈方向定型；避免仅凭已过买点复读。"
        )
    return out


def heuristic_verdict(r: AnalyzeResponse) -> dict[str, Any]:
    buys, sells = r.buy_signals, r.sell_signals
    all_s: list[Signal] = [*buys, *sells]
    reasons: list[str] = []
    latest: Optional[Signal] = None

    if not all_s:
        reasons.append("当前未输出买卖点：中枢/离开段/背驰证据不足或级别不匹配。")
        reasons.append(
            "后续可先跟踪：级别延续时是否走出新的分型—笔—中枢闭环，再讨论可操作语境（不构成投资建议）。"
        )
        if r.lines_form and r.lines_form.detail_zh:
            reasons.append(f"走势形态：{r.lines_form.primary} — {r.lines_form.detail_zh[:120]}")
        hints = AiVerdictPriceHints(
            note_zh="无明显信号价可依，参考价留空；不构成投资建议。"
        )
        return {
            "bias": "neutral",
            "confidence": 0.35,
            "summary_zh": "结构信号不足，后续以观望与边界跟踪为主。",
            "reasons_zh": reasons[:8],
            "price_hints": hints,
        }

    latest = max(all_s, key=lambda s: s.idx)
    kind_cn = {
        "first": "一类",
        "second": "二类",
        "second_extend": "二类延伸",
        "third": "三类",
        "second_class": "类二",
        "third_class": "类三",
        "td9": "TD9",
    }.get(latest.kind, latest.kind)

    if latest.side == SignalSide.BUY:
        bias: _BIAS = "long"
        summary = (
            f"偏多观察：后续先看下探/回抽与中枢边界如何演化；最近买点（{kind_cn}）仅作结构锚点。"
        )
        reasons.append(
            f"锚点（已标注）：买侧 {kind_cn}（{latest.time}），价≈{latest.price:.8f}——用于对齐价位，不代表此刻必须入场。"
        )
    else:
        bias = "short"
        summary = (
            f"偏空观察：后续先看上冲/回抽与中枢边界如何演化；最近卖点（{kind_cn}）仅作结构锚点。"
        )
        reasons.append(
            f"锚点（已标注）：卖侧 {kind_cn}（{latest.time}），价≈{latest.price:.8f}——用于对齐价位，不代表此刻必须离场。"
        )

    reasons.extend(_forward_reason_lines(r, bias=bias))

    rel = r.action_focus.primary_pivot.relation if r.action_focus else "none"
    if rel == "inside":
        reasons.append("本级快照：价在最近参考中枢区间内，震荡为主，突破方向待确认。")
    elif rel == "above":
        reasons.append("本级快照：价在参考中枢上方，偏强离开/回踩测试语境。")
    elif rel == "below":
        reasons.append("本级快照：价在参考中枢下方，偏弱离开/反抽测试语境。")

    adv = r.advanced_context
    if adv and adv.trend_recursion and adv.trend_recursion.composite:
        comp = adv.trend_recursion.composite
        reasons.append(f"跨级编码：{comp}；解读时优先看各级边界与离开段是否共振，而非单点回放。")
        if comp == "cross_level_divergent":
            summary = summary.replace("。", "（跨级张力大，宜看边界确认）。")

    active = r.action_focus.active_bi if r.action_focus else None
    if active and latest:
        pen_up = active.direction == Direction.UP
        late_buy = latest.side == SignalSide.BUY
        if pen_up and not late_buy:
            reasons.append(
                "未完成笔向上与更近的卖侧锚点并存：后续重点看这笔是否延伸、或被反向分型终结，以及 ZG/ZD 测试结果。"
            )
        if not pen_up and late_buy:
            reasons.append(
                "未完成笔向下与更近的买侧锚点并存：后续重点看这笔是否延伸、或被反向分型终结，以及 ZG/ZD 测试结果。"
            )

    conf = 0.55 if len(reasons) >= 3 else 0.5
    hints = _heuristic_price_hints(r, bias=bias, latest=latest)
    if hints.note_zh:
        hints = hints.model_copy(
            update={
                "note_zh": hints.note_zh
                + " 结论侧重「后续关键位与条件」，已过信号仅作锚点。"
            }
        )
    return {
        "bias": bias,
        "confidence": conf,
        "summary_zh": summary[:120],
        "reasons_zh": reasons[:8],
        "price_hints": hints,
    }


def _parse_float_opt(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_glm_json(content: str) -> Optional[dict[str, Any]]:
    text = (content or "").strip()
    if not text:
        return None
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalize_verdict_dict(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    b = raw.get("bias")
    if b not in ("long", "short", "neutral"):
        return None
    conf = raw.get("confidence")
    try:
        cf = float(conf)
        cf = max(0.0, min(1.0, cf))
    except (TypeError, ValueError):
        cf = 0.55
    summ = str(raw.get("summary_zh") or "").strip()
    if not summ:
        return None
    rs = raw.get("reasons_zh")
    if not isinstance(rs, list):
        rs = []
    reasons = [str(x).strip() for x in rs if str(x).strip()][:8]
    if not reasons:
        reasons = [summ]
    hints = AiVerdictPriceHints(
        buy_focus_price=_parse_float_opt(raw.get("buy_focus_price")),
        sell_focus_price=_parse_float_opt(raw.get("sell_focus_price")),
        stop_loss_buy=_parse_float_opt(raw.get("stop_loss_buy")),
        stop_loss_sell=_parse_float_opt(raw.get("stop_loss_sell")),
        note_zh=str(raw.get("price_note_zh") or "").strip(),
    )
    if not hints.note_zh:
        hints = hints.model_copy(
            update={
                "note_zh": "以上价位为模型结合输入结构的推演参考，不保证成交，不构成投资建议。"
            }
        )
    return {
        "bias": b,
        "confidence": cf,
        "summary_zh": summ,
        "reasons_zh": reasons,
        "price_hints": hints,
    }


async def _call_zhipu_anthropic_messages(
    user_content: str, *, api_key: str, model: str
) -> str:
    """智谱 Claude API 兼容：`POST {base}/v1/messages`，见 https://docs.bigmodel.cn/cn/guide/develop/claude/introduction"""
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("ZHIPU_API_KEY empty")
    base = settings.zhipu_api_base.rstrip("/")
    url = f"{base}/v1/messages"
    timeout = settings.ai_verdict_timeout_seconds
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 2048,
        "temperature": 0.2,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {
        "x-api-key": key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    blocks = data.get("content")
    if not isinstance(blocks, list) or not blocks:
        raise RuntimeError("empty anthropic content")
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("empty text in content blocks")
    return text


async def _call_zhipu_openai_chat(user_content: str, *, api_key: str, model: str) -> str:
    """旧版智谱 OpenAI 兼容：`POST .../chat/completions`。"""
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("ZHIPU_API_KEY empty")
    base = settings.zhipu_api_base.rstrip("/")
    url = f"{base}/chat/completions"
    timeout = settings.ai_verdict_timeout_seconds
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("empty choices")
    msg = choices[0].get("message") or {}
    content = msg.get("content") or ""
    if not content:
        raise RuntimeError("empty content")
    return str(content)


async def _call_zhipu_llm(user_content: str, *, api_key: str, model: str) -> str:
    if settings.zhipu_api_mode == "openai_compat":
        return await _call_zhipu_openai_chat(user_content, api_key=api_key, model=model)
    return await _call_zhipu_anthropic_messages(user_content, api_key=api_key, model=model)


def _response_from_fallback(fallback: dict[str, Any], **kwargs: Any) -> AiVerdictResponse:
    ph = fallback.get("price_hints")
    if not isinstance(ph, AiVerdictPriceHints):
        ph = None
    return AiVerdictResponse(
        bias=fallback["bias"],
        confidence=float(fallback["confidence"]),
        summary_zh=fallback["summary_zh"],
        reasons_zh=list(fallback["reasons_zh"]),
        price_hints=ph,
        **kwargs,
    )


async def verdict_from_analyze_payload(body: dict[str, Any]) -> AiVerdictResponse:
    clean, glm_opt = pop_glm_request_options(body)
    merged = merge_verdict_analysis_dict(clean)
    try:
        analysis = AnalyzeResponse.model_validate(merged)
    except ValidationError as exc:
        return AiVerdictResponse(
            success=False,
            source="disabled",
            bias="neutral",
            confidence=0.0,
            summary_zh="请求体无法解析为分析结果。",
            reasons_zh=[],
            price_hints=None,
            error_detail=str(exc.errors())[:500],
        )

    full_ctx = bool(glm_opt["full_context"])
    ctx = build_glm_context(analysis, full_context=full_ctx)
    fallback = heuristic_verdict(analysis)

    eff_key = (glm_opt["api_key"] or settings.zhipu_api_key or "").strip()
    eff_model = (glm_opt["model"] or settings.zhipu_model or "glm-4.7").strip()

    if not eff_key:
        return _response_from_fallback(
            fallback,
            success=True,
            source="heuristic_fallback",
            error_detail="未配置 GLM API Key：可在请求体传入 glm_api_key，或设置环境变量 CHANLAN_ZHIPU_API_KEY。",
        )

    user_payload = (
        "以下为缠论程序输出的结构化数据（JSON）。请严格按系统提示只输出一个 JSON 对象。\n"
        + json.dumps(ctx, ensure_ascii=False)
    )
    try:
        raw_text = await _call_zhipu_llm(user_payload, api_key=eff_key, model=eff_model)
        parsed = _parse_glm_json(raw_text)
        norm = _normalize_verdict_dict(parsed) if parsed else None
        if norm:
            return AiVerdictResponse(
                success=True,
                source="glm",
                bias=norm["bias"],
                confidence=float(norm["confidence"]),
                summary_zh=norm["summary_zh"],
                reasons_zh=list(norm["reasons_zh"]),
                price_hints=norm["price_hints"],
                model_name=eff_model,
            )
        fb = {**fallback, "confidence": float(fallback["confidence"]) * 0.85}
        return _response_from_fallback(
            fb,
            success=True,
            source="heuristic_fallback",
            model_name=eff_model,
            error_detail="GLM 返回无法解析为 JSON，已降级为规则摘要。",
        )
    except Exception as exc:  # noqa: BLE001
        fb = {**fallback, "confidence": float(fallback["confidence"]) * 0.85}
        return _response_from_fallback(
            fb,
            success=True,
            source="heuristic_fallback",
            model_name=eff_model,
            error_detail=str(exc)[:500],
        )
