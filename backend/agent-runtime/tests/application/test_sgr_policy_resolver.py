from __future__ import annotations

import pytest

from cys_core.application.reasoning.sgr_policy import resolve_sgr_policy
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.reasoning.sgr_models import SgrPolicy


@pytest.mark.unit
def test_resolve_sgr_profile_overrides_agent():
    profile = ProfilePolicyPayload(sgr=SgrPolicy(enabled=True, mode="sgr_iron"))
    agent = AgentDefinition(
        name="soc",
        description="",
        role="worker",
        system_prompt="",
        reasoning_mode="sgr_hybrid",
    )
    resolved = resolve_sgr_policy(profile_policy=profile, agent=agent, use_sgr_reasoning=True)
    assert resolved.enabled
    assert resolved.mode == "sgr_iron"


@pytest.mark.unit
def test_resolve_sgr_agent_when_profile_off():
    profile = ProfilePolicyPayload(sgr=SgrPolicy(enabled=False, mode="off"))
    agent = AgentDefinition(
        name="soc",
        description="",
        role="worker",
        system_prompt="",
        reasoning_mode="sgr_hybrid",
    )
    resolved = resolve_sgr_policy(profile_policy=profile, agent=agent, use_sgr_reasoning=True)
    assert resolved.enabled
    assert resolved.mode == "sgr_hybrid"


@pytest.mark.unit
def test_resolve_sgr_kill_switch():
    agent = AgentDefinition(
        name="soc",
        description="",
        role="worker",
        system_prompt="",
        reasoning_mode="sgr_hybrid",
    )
    resolved = resolve_sgr_policy(agent=agent, use_sgr_reasoning=False)
    assert not resolved.enabled
