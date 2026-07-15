from __future__ import annotations

from cys_core.domain.catalog.models import McpServerEntry, PlanCatalogEntry, SkillCatalogEntry


def fan_out_secondary_catalogs(
    *,
    skills: list[SkillCatalogEntry] | None = None,
    plans: list[PlanCatalogEntry] | None = None,
    mcp_servers: list[McpServerEntry] | None = None,
) -> None:
    if not (skills or plans or mcp_servers):
        return
    from cys_core.infrastructure.catalog.registry_factory import (
        get_mcp_catalog,
        get_plan_catalog,
        get_skill_catalog,
    )

    skill_catalog = get_skill_catalog()
    plan_catalog = get_plan_catalog()
    mcp_catalog = get_mcp_catalog()
    for skill in skills or []:
        skill_catalog.upsert_skill(skill)
    for plan in plans or []:
        plan_catalog.upsert_plan(plan)
    for server in mcp_servers or []:
        mcp_catalog.upsert_server(server)
