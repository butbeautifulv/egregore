"""Resolve worker persona from workspace_agent overlay when present (ADR-005)."""

from __future__ import annotations

from cys_core.application.ports.agent_registry import AgentRegistryPort
from cys_core.application.ports.workspace_store import WorkspaceStorePort
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.security.system_prompt_assembler import assemble_trusted_system_context


def resolve_worker_agent_definition(
    *,
    persona: str,
    workspace_id: str,
    registry: AgentRegistryPort,
    workspace_store: WorkspaceStorePort | None = None,
) -> AgentDefinition:
    """Platform seed with optional workspace_agent persona/tools/skills overlay."""
    platform = registry.get(persona)
    ws_id = (workspace_id or "").strip()
    if not ws_id or workspace_store is None:
        return platform
    ws_agent = workspace_store.get_agent(ws_id, persona)
    if ws_agent is None:
        return platform
    persona_prompt = (ws_agent.persona_prompt or platform.persona_prompt or "").strip()
    if not persona_prompt:
        persona_prompt = platform.persona_prompt
    ctx = assemble_trusted_system_context(persona_prompt, language=ws_agent.language or platform.language)
    tools = list(ws_agent.tools) if ws_agent.tools else list(platform.tools)
    skills = list(ws_agent.skills) if ws_agent.skills else list(platform.skills)
    return platform.model_copy(
        update={
            "persona_prompt": persona_prompt,
            "system_prompt": ctx.text,
            "system_prompt_digest": ctx.digest,
            "language": ws_agent.language or platform.language,
            "tools": tools,
            "skills": skills,
        }
    )
