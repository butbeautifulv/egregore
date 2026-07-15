from __future__ import annotations

from collections.abc import Callable

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.catalog_audit import CatalogAuditPort
from cys_core.application.ports.tool_catalog import ToolCatalogPort
from cys_core.domain.catalog.models import (
    AgentCatalogEntry,
    McpServerEntry,
    PlanCatalogEntry,
    ProfilePack,
    SkillCatalogEntry,
    ToolCatalogEntry,
)
from cys_core.application.ports.catalog_write_gate import CatalogWriteGatePort


class CatalogMutationService:
    """Unified write path: catalog mutation + audit + reload."""

    def __init__(
        self,
        *,
        write_gate: CatalogWriteGatePort,
        agent_catalog: AgentCatalogPort,
        tool_catalog: ToolCatalogPort,
        audit: CatalogAuditPort | None = None,
        reload: Callable[[], None] | None = None,
    ) -> None:
        self._write_gate = write_gate
        self._agents = agent_catalog
        self._tools = tool_catalog
        self._audit = audit
        self._reload = reload or (lambda: None)

    def upsert_agent(self, entry: AgentCatalogEntry, *, actor: str = "api") -> AgentCatalogEntry:
        return self._write_gate.upsert_agent(entry, actor=actor)

    def upsert_skill(self, entry: SkillCatalogEntry, *, actor: str = "api") -> SkillCatalogEntry:
        return self._write_gate.upsert_skill(entry, actor=actor)

    def approve_skill(
        self, skill_id: str, *, profile_id: str, actor: str = "api"
    ) -> SkillCatalogEntry:
        return self._write_gate.approve_skill(skill_id, profile_id=profile_id, actor=actor)

    def upsert_plan(self, entry: PlanCatalogEntry, *, actor: str = "api") -> PlanCatalogEntry:
        return self._write_gate.upsert_plan(entry, actor=actor)

    def upsert_mcp_server(self, entry: McpServerEntry, *, actor: str = "api") -> McpServerEntry:
        return self._write_gate.upsert_mcp_server(entry, actor=actor)

    def upsert_tool(self, entry: ToolCatalogEntry, *, actor: str = "api") -> ToolCatalogEntry:
        saved = self._tools.upsert_tool(entry)
        if self._audit is not None:
            self._audit.record_change(
                "upsert",
                agent=entry.id,
                actor=actor,
                details={"name": entry.name},
                resource_type="tool",
                resource_id=entry.id,
            )
        self._reload()
        return saved

    def upsert_profile(self, profile: ProfilePack, *, actor: str = "api") -> ProfilePack:
        saved = self._agents.upsert_profile(profile)
        if self._audit is not None:
            self._audit.record_change(
                "upsert",
                agent=profile.id,
                actor=actor,
                resource_type="profile",
                resource_id=profile.id,
            )
        self._reload()
        return saved

    def delete_agent(self, name: str, *, profile_id: str, actor: str = "api") -> bool:
        return self._write_gate.delete_agent(name, profile_id=profile_id, actor=actor)

    def seed_pack(
        self,
        profile: ProfilePack,
        entries: list,
        *,
        skills: list | None = None,
        plans: list | None = None,
        mcp_servers: list | None = None,
        tools: list | None = None,
        actor: str = "seed",
    ) -> dict[str, int]:
        self._agents.seed(
            entries,
            profile,
            skills=skills or [],
            plans=plans or [],
            mcp_servers=mcp_servers or [],
        )
        if tools:
            self._tools.seed(tools)
        if self._audit is not None:
            self._audit.record_change("seed", agent=profile.id, actor=actor, resource_type="profile", resource_id=profile.id)
        self._reload()
        return {
            "seeded": len(entries),
            "skills": len(skills or []),
            "plans": len(plans or []),
            "mcp_servers": len(mcp_servers or []),
            "tools": len(tools or []),
        }

    def delete_skill(self, skill_id: str, *, profile_id: str, actor: str = "api") -> bool:
        return self._write_gate.delete_skill(skill_id, profile_id=profile_id, actor=actor)
