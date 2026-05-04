from __future__ import annotations

from app.services.fake_bi import build_fake_bis


def test_fake_bis_empty_inputs() -> None:
    assert build_fake_bis([], [], []) == []
