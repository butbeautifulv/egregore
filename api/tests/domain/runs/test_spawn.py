from __future__ import annotations

import pytest

from cys_core.domain.runs.spawn import MAX_SPAWN_DEPTH, SpawnWorkerPayload, sanitize_persona_overlay
from cys_core.domain.runs.models import RunContext, InteractionMode


@pytest.mark.unit
def test_sanitize_persona_overlay_strips_control_chars():
    text = "ok\x00bad"
    assert "\x00" not in sanitize_persona_overlay(text)


@pytest.mark.unit
def test_spawn_payload_caps_overlay():
    parent = RunContext.one_shot_job("j1", mode=InteractionMode.AGENT)
    payload = SpawnWorkerPayload(
        parent_context=parent,
        persona="soc",
        sub_goal="work",
        persona_overlay="x" * 5000,
    )
    assert len(payload.persona_overlay) == 2000


@pytest.mark.unit
def test_max_spawn_depth_constant():
    assert MAX_SPAWN_DEPTH == 5
