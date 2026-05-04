"""启发式结构打分占位实现（非训练模型）。"""

from __future__ import annotations

from app.core.models import AiStructureHintRequest, AiStructureHintResponse


def structure_hint(req: AiStructureHintRequest) -> AiStructureHintResponse:
    raw = (
        req.pivot_count * 3.0
        + req.divergence_count * 10.0
        + min(35.0, req.buy_signal_count * 5.0)
        + min(35.0, req.sell_signal_count * 5.0)
    )
    score = min(100.0, raw)
    notes: list[str] = []
    if req.pivot_count == 0:
        notes.append("暂无中枢结构：买卖点可信度受限")
    if req.divergence_count == 0:
        notes.append("未发现背驰候选：一类买卖点证据偏弱")
    if req.buy_signal_count == 0 and req.sell_signal_count == 0:
        notes.append("无买卖点输出：可能仍在构筑中枢或级别不匹配")
    if not notes:
        notes.append("结构性要素齐备程度中等偏高（仍为启发式评分）")
    return AiStructureHintResponse(score_0_100=score, notes=notes)
