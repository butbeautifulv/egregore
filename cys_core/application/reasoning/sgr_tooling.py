from __future__ import annotations

from cys_core.application.policy_resolver import get_profile_policy_resolver
from cys_core.application.reasoning.sgr_policy import ResolvedSgrPolicy, resolve_sgr_policy
from cys_core.application.runtime_config import get_sgr_default_mode, get_use_sgr_reasoning
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.policy.pure import filter_tools_pure
from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL, SgrMode


def normalize_sgr_mode(mode: str) -> SgrMode:
    """Map env aliases (soft/iron) to domain SgrMode."""
    key = (mode or "off").lower().strip()
    if key in {"soft", "sgr_hybrid", "hybrid"}:
        return "sgr_hybrid"
    if key in {"iron", "sgr_iron"}:
        return "sgr_iron"
    if key in {"off", "sgr_off"}:
        return "off"
    return "off"


def resolve_sgr_for_agent(
    defn: AgentDefinition,
    profile_id: str,
) -> ResolvedSgrPolicy:
    profile_policy = get_profile_policy_resolver().policy(profile_id)
    default_mode = normalize_sgr_mode(get_sgr_default_mode())
    return resolve_sgr_policy(
        profile_policy=profile_policy,
        agent=defn,
        use_sgr_reasoning=get_use_sgr_reasoning(),
        default_mode=default_mode,
    )


def resolve_agent_tool_names(defn: AgentDefinition, profile_id: str) -> list[str]:
    """Profile-filtered tool names with reasoning_step when SGR is enabled."""
    profile_policy = get_profile_policy_resolver().policy(profile_id)
    tool_names = filter_tools_pure(defn.tools, profile_id, policy=profile_policy)
    sgr = resolve_sgr_for_agent(defn, profile_id)
    if sgr.enabled and REASONING_STEP_TOOL not in tool_names:
        tool_names = [REASONING_STEP_TOOL, *tool_names]
    return tool_names


def scope_allowed_tools(defn: AgentDefinition, profile_id: str) -> list[str]:
    """Scope middleware allowlist — must include injected SGR tools."""
    sgr = resolve_sgr_for_agent(defn, profile_id)
    allowed = list(defn.allowed_tools or defn.tools)
    if sgr.enabled and REASONING_STEP_TOOL not in allowed:
        allowed = [REASONING_STEP_TOOL, *allowed]
    return allowed
