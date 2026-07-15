from __future__ import annotations

from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.domain.catalog.models import (
    McpServerEntry,
    PlanCatalogEntry,
    SkillCatalogEntry,
    StagingStatus,
    ToolCatalogEntry,
)
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID, resolve_profile_id


def _resolve(body: dict, *, explicit_profile_id: str | None = None) -> str:
    return resolve_profile_id(explicit=explicit_profile_id, payload=body)


class UpsertSkill:
    def __init__(self, mutation: CatalogMutationService) -> None:
        self._mutation = mutation

    def execute(
        self,
        skill_id: str,
        body: dict,
        *,
        actor: str = "api",
    ) -> SkillCatalogEntry:
        entry = SkillCatalogEntry(
            id=skill_id,
            name=body.get("name") or skill_id,
            description=body.get("description", ""),
            body=body.get("body", ""),
            profile_id=_resolve(body),
            trust_tier=body.get("trust_tier", "community"),
            staging_status=StagingStatus(body.get("staging_status", "draft")),
        )
        return self._mutation.upsert_skill(entry, actor=actor)


class UpsertPlan:
    def __init__(self, mutation: CatalogMutationService) -> None:
        self._mutation = mutation

    def execute(
        self,
        plan_id: str,
        body: dict,
        *,
        actor: str = "api",
    ) -> PlanCatalogEntry:
        entry = PlanCatalogEntry(
            id=plan_id,
            name=body.get("name") or plan_id,
            description=body.get("description", ""),
            rules=body.get("rules", []),
            profile_id=_resolve(body),
            enabled=body.get("enabled", True),
        )
        return self._mutation.upsert_plan(entry, actor=actor)


class UpsertMcpServer:
    def __init__(self, mutation: CatalogMutationService) -> None:
        self._mutation = mutation

    def execute(
        self,
        server_id: str,
        body: dict,
        *,
        actor: str = "api",
    ) -> McpServerEntry:
        entry = McpServerEntry(
            id=server_id,
            url=body["url"],
            trust_tier=body.get("trust_tier", "internal"),
            allowed_tools=body.get("allowed_tools", []),
            enabled=body.get("enabled", True),
            profile_id=_resolve(body),
        )
        return self._mutation.upsert_mcp_server(entry, actor=actor)


class UpsertTool:
    def __init__(self, mutation: CatalogMutationService) -> None:
        self._mutation = mutation

    def execute(
        self,
        tool_id: str,
        body: dict,
        *,
        actor: str = "api",
    ) -> ToolCatalogEntry:
        entry = ToolCatalogEntry(
            id=tool_id,
            name=body.get("name") or tool_id,
            description=body.get("description", ""),
            risk_tier=body.get("risk_tier", "medium"),
            handler=body.get("handler", "builtin"),
            enabled=body.get("enabled", True),
            profile_id=_resolve(body),
        )
        return self._mutation.upsert_tool(entry, actor=actor)
