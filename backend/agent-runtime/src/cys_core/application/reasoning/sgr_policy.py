from __future__ import annotations

from dataclasses import dataclass

from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.catalog.models import ProfilePolicyPayload
from cys_core.domain.reasoning.sgr_models import SgrMode, SgrPolicy


@dataclass(frozen=True)
class ResolvedSgrPolicy:
    enabled: bool
    mode: SgrMode
    require_before_action: bool


def resolve_sgr_policy(
    *,
    profile_policy: ProfilePolicyPayload | None = None,
    agent: AgentDefinition | None = None,
    use_sgr_reasoning: bool = True,
    default_mode: SgrMode = "off",
) -> ResolvedSgrPolicy:
    """Precedence: profile.sgr → agent.reasoning_mode → env default."""
    if not use_sgr_reasoning:
        return ResolvedSgrPolicy(enabled=False, mode="off", require_before_action=True)

    sgr = profile_policy.sgr if profile_policy else SgrPolicy()
    if sgr.enabled and sgr.mode != "off":
        return ResolvedSgrPolicy(
            enabled=True,
            mode=sgr.mode,
            require_before_action=sgr.require_before_action,
        )

    agent_mode: SgrMode = getattr(agent, "reasoning_mode", "off") if agent else "off"
    if agent_mode != "off":
        return ResolvedSgrPolicy(
            enabled=True,
            mode=agent_mode,
            require_before_action=sgr.require_before_action,
        )

    if default_mode != "off":
        return ResolvedSgrPolicy(
            enabled=True,
            mode=default_mode,
            require_before_action=sgr.require_before_action,
        )

    return ResolvedSgrPolicy(enabled=False, mode="off", require_before_action=sgr.require_before_action)
