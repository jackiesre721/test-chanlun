"""analyze_disk_cache：禁用 / glm 跳过 / 损坏文件容错。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.models import AnalyzeRequest, GlmVerdictInlineOptions
from app.services import analyze_disk_cache as adc


def test_load_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "analyze_disk_cache_enabled", False)
    req = AnalyzeRequest()
    assert adc.load_cached_analyze_result(request=req, eff_limit=1000, anchor_open_time_ms=123) is None


def test_load_returns_none_when_inline_glm(monkeypatch):
    monkeypatch.setattr(settings, "analyze_disk_cache_enabled", True)
    req = AnalyzeRequest(glm_verdict=GlmVerdictInlineOptions(glm_full_context=False))
    assert adc.load_cached_analyze_result(request=req, eff_limit=500, anchor_open_time_ms=1) is None


def test_load_invalid_file_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "analyze_disk_cache_enabled", True)
    monkeypatch.setattr(settings, "analyze_disk_cache_dir", str(tmp_path))
    monkeypatch.setattr(settings, "segment_engine", "legacy")
    req = AnalyzeRequest()
    eff = 1000
    ot = 999_888
    key = adc._cache_key(
        symbol=req.symbol,
        interval=req.interval,
        eff_limit=eff,
        segment_engine=settings.segment_engine,
        anchor_open_time_ms=ot,
    )
    (tmp_path / f"{key}.json").write_text("{not-json", encoding="utf-8")
    assert adc.load_cached_analyze_result(request=req, eff_limit=eff, anchor_open_time_ms=ot) is None


def test_save_skips_when_inline_glm(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "analyze_disk_cache_enabled", True)
    monkeypatch.setattr(settings, "analyze_disk_cache_dir", str(tmp_path))
    monkeypatch.setattr(settings, "segment_engine", "legacy")
    req = AnalyzeRequest(glm_verdict=GlmVerdictInlineOptions(glm_full_context=False))
    adc.save_cached_analyze_result(
        request=req,
        eff_limit=500,
        anchor_open_time_ms=123,
        response=MagicMock(),
    )
    assert list(tmp_path.glob("*.json")) == []
