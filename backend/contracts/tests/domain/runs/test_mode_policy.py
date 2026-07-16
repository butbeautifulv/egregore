from __future__ import annotations

import pytest

from cys_core.domain.runs.mode_policy import ModePolicy, _is_mutating
from cys_core.domain.runs.models import InteractionMode


@pytest.mark.unit
def test_mode_policy_plan_blocks_mutating_tools():
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "spawn_worker") is False
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "ask_user") is False
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "run_scan") is False
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "search_personas") is True


@pytest.mark.unit
def test_mode_policy_ask_read_only():
    assert ModePolicy.allow_tool(InteractionMode.ASK, "rag_query") is True
    assert ModePolicy.allow_tool(InteractionMode.ASK, "spawn_worker") is False
    assert ModePolicy.allow_tool(InteractionMode.ASK, "search_tools") is True


@pytest.mark.unit
def test_mode_policy_bus_and_spawn():
    assert ModePolicy.allow_bus_message(InteractionMode.PLAN, "spawn_worker") is False
    assert ModePolicy.allow_bus_message(InteractionMode.ASK, "spawn_worker") is False
    assert ModePolicy.allow_bus_message(InteractionMode.AGENT, "spawn_worker") is True
    assert ModePolicy.allow_spawn(InteractionMode.PLAN) is False
    assert ModePolicy.allow_spawn(InteractionMode.AGENT) is True
    assert ModePolicy.allow_spawn(InteractionMode.DEBUG) is True
    assert ModePolicy.allow_spawn(None) is True


@pytest.mark.unit
def test_is_mutating_helpers():
    assert _is_mutating("spawn_worker") is True
    assert _is_mutating("write_file") is True
    assert _is_mutating("rag_query") is False

    assert ModePolicy.allow_tool(None, "spawn_worker") is True
    assert ModePolicy.allow_bus_message(None, "spawn_worker") is True
    assert ModePolicy.allow_tool(InteractionMode.AGENT, "spawn_worker") is True
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "delegate_research") is False
    assert ModePolicy.allow_tool(InteractionMode.AGENT, "load_skill") is True
    assert ModePolicy.allow_tool(InteractionMode.PLAN, "load_skill") is True


@pytest.mark.unit
def test_mode_policy_ask_allows_research_tools():
    assert ModePolicy.allow_tool(InteractionMode.ASK, "web_search") is True
    assert ModePolicy.allow_tool(InteractionMode.ASK, "read_document") is True
    assert ModePolicy.allow_tool(InteractionMode.ASK, "reasoning_check") is True
