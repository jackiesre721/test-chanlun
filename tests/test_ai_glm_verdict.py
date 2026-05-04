"""ai_glm_verdict：压缩语境、merge 缺省字段、规则降级（不调用外网）。"""

from __future__ import annotations

import asyncio

import pytest

from app.core.models import (
    ActionFocus,
    ActionFocusPivotRef,
    ActionFocusPivotSlot,
    AnalyzeRequest,
    AnalyzeResponse,
    Candle,
    GlmVerdictInlineOptions,
    LinesFormSummary,
    MacdPoint,
    Market,
    Signal,
    SignalSide,
    TdSummary,
)
from app.services.ai_glm_verdict import (
    compact_for_glm,
    heuristic_verdict,
    merge_verdict_analysis_dict,
    pop_glm_request_options,
    verdict_from_analyze_payload,
)


def _minimal_body(**overrides):
    base = {
        "success": True,
        "market": "crypto",
        "symbol": "BTCUSDT",
        "interval": "60",
        "current_price": 100.0,
        "data_source": "test",
        "rules_version": "t",
        "segment_engine": "legacy",
        "lines_form": {"primary": "mixed", "detail_zh": ""},
        "kline_data": [
            {
                "open_time": 1,
                "time": "t0",
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 1.0,
            }
        ],
        "macd_data": [{"dif": 0.0, "dea": 0.0, "hist": 0.0}],
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
        "td_summary": {"setup_up": 0, "setup_down": 0},
        "action_focus": {
            "last_bar_index": 0,
            "recent_window_bars": 20,
            "current_price": 100.0,
            "primary_pivot": {"relation": "none"},
            "higher_pivot": {"relation": "none"},
        },
    }
    base.update(overrides)
    return base


def test_analyze_request_inline_glm_optional():
    r = AnalyzeRequest(
        symbol="BTCUSDT",
        interval="60",
        glm_verdict=GlmVerdictInlineOptions(glm_full_context=False, glm_api_key="x"),
    )
    assert r.glm_verdict is not None
    assert r.glm_verdict.glm_full_context is False
    assert r.glm_verdict.glm_api_key == "x"


def test_verdict_without_api_key_uses_heuristic():
    body = _minimal_body(
        buy_signals=[
            {
                "side": "BUY",
                "kind": "first",
                "idx": 5,
                "time": "t",
                "price": 99.0,
                "description": "d",
                "strength": 1.0,
            }
        ],
    )
    r = asyncio.run(verdict_from_analyze_payload(body))
    assert r.success is True
    assert r.source == "heuristic_fallback"
    assert r.bias == "long"
    assert r.summary_zh
    assert "glm_api_key" in r.error_detail or "ZHIPU" in r.error_detail or "API Key" in r.error_detail


def test_pop_glm_strips_meta_before_merge():
    body = {**_minimal_body(), "glm_api_key": "secret", "glm_model": "glm-4-x", "glm_full_context": False}
    clean, opt = pop_glm_request_options(body)
    assert "glm_api_key" not in clean
    assert opt["api_key"] == "secret"
    assert opt["model"] == "glm-4-x"
    assert opt["full_context"] is False


def test_compact_for_glm_omits_large_series():
    c = Candle(
        open_time=1,
        time="t",
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=1.0,
    )
    af = ActionFocus(
        last_bar_index=1,
        recent_window_bars=30,
        current_price=100.0,
        primary_pivot=ActionFocusPivotSlot(
            relation="inside",
            pivot=ActionFocusPivotRef(level="bi", zd=99.0, zg=101.0, start_idx=0, end_idx=1),
        ),
        higher_pivot=ActionFocusPivotSlot(relation="none"),
    )
    ar = AnalyzeResponse(
        market=Market.CRYPTO,
        symbol="BTCUSDT",
        interval="60",
        current_price=100.0,
        data_source="x",
        rules_version="rv",
        lines_form=LinesFormSummary(primary="up"),
        kline_data=[c, c],
        macd_data=[MacdPoint(dif=0, dea=0, hist=0)],
        fractals=[],
        bis=[],
        active_bi=None,
        segments=[],
        divergences=[],
        bis_lv2=[],
        zhongshus=[],
        zhongshus_lv2=[],
        buy_signals=[
            Signal(side=SignalSide.BUY, kind="first", idx=1, time="t", price=1.0, description="x", strength=0.5)
        ],
        sell_signals=[],
        td_summary=TdSummary(setup_up=0, setup_down=0),
        action_focus=af,
    )
    d = compact_for_glm(ar)
    assert "kline_data" not in d
    assert d["symbol"] == "BTCUSDT"
    assert d["action_focus"]["primary"]["relation"] == "inside"


def test_merge_defaults_fills_arrays():
    m = merge_verdict_analysis_dict({"symbol": "BTCUSDT", "interval": "15"})
    assert m["bis"] == []
    assert m["buy_signals"] == []


def test_heuristic_neutral_when_no_signals():
    c = Candle(
        open_time=1,
        time="t",
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=1.0,
    )
    af = ActionFocus(
        last_bar_index=0,
        recent_window_bars=20,
        current_price=1.0,
        primary_pivot=ActionFocusPivotSlot(relation="none"),
        higher_pivot=ActionFocusPivotSlot(relation="none"),
    )
    ar = AnalyzeResponse(
        market=Market.CRYPTO,
        symbol="ETHUSDT",
        interval="240",
        current_price=1.0,
        data_source="x",
        rules_version="rv",
        lines_form=LinesFormSummary(primary="flat", detail_zh="箱体"),
        kline_data=[c],
        macd_data=[MacdPoint(dif=0, dea=0, hist=0)],
        fractals=[],
        bis=[],
        active_bi=None,
        segments=[],
        divergences=[],
        bis_lv2=[],
        zhongshus=[],
        zhongshus_lv2=[],
        buy_signals=[],
        sell_signals=[],
        td_summary=TdSummary(setup_up=0, setup_down=0),
        action_focus=af,
    )
    h = heuristic_verdict(ar)
    assert h["bias"] == "neutral"
