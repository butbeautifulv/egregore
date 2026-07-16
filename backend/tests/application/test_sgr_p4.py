from __future__ import annotations

from cys_core.application.reasoning.sgr_iron_policy import check_iron_tool_allowed
from cys_core.application.reasoning.sgr_tooling import (
    normalize_sgr_mode,
    resolve_agent_tool_names,
    scope_allowed_tools,
)
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL


def test_normalize_sgr_mode_aliases() -> None:
    assert normalize_sgr_mode("soft") == "sgr_hybrid"
    assert normalize_sgr_mode("iron") == "sgr_iron"
    assert normalize_sgr_mode("off") == "off"


def test_resolve_agent_tool_names_injects_reasoning_step(monkeypatch) -> None:
    from cys_core.application.reasoning import sgr_policy as mod

    monkeypatch.setattr(
        mod,
        "resolve_sgr_policy",
        lambda **_kw: mod.ResolvedSgrPolicy(enabled=True, mode="sgr_hybrid", require_before_action=True),
    )
    defn = AgentDefinition(
        name="t",
        description="d",
        role="worker",
        system_prompt="x",
        system_prompt_digest="dig",
        schema_name=None,
        tools=["web_search"],
        skills=[],
        hitl_tools={},
        reasoning_mode="sgr_hybrid",
    )
    names = resolve_agent_tool_names(defn, "general-assistant")
    assert REASONING_STEP_TOOL in names


def test_scope_allowed_tools_includes_reasoning_step(monkeypatch) -> None:
    from cys_core.application.reasoning import sgr_policy as mod

    monkeypatch.setattr(
        mod,
        "resolve_sgr_policy",
        lambda **_kw: mod.ResolvedSgrPolicy(enabled=True, mode="sgr_iron", require_before_action=True),
    )
    defn = AgentDefinition(
        name="t",
        description="d",
        role="worker",
        system_prompt="x",
        system_prompt_digest="dig",
        schema_name=None,
        tools=["web_search"],
        skills=[],
        hitl_tools={},
        reasoning_mode="sgr_iron",
    )
    allowed = scope_allowed_tools(defn, "general-assistant")
    assert REASONING_STEP_TOOL in allowed


def test_iron_policy_blocks_unknown_tool() -> None:
    decision = check_iron_tool_allowed(
        tool_name="spawn_subagent",
        allowed_tools=["web_search"],
        mode="sgr_iron",
        profile_id="gaia-benchmark",
    )
    assert not decision.allowed
