from __future__ import annotations

from cys_core.application.runtime_config import (
    get_postgres_url,
    get_use_dynamic_catalog,
    get_use_memory_fallback,
)
from cys_core.infrastructure.catalog.audit_adapter import InMemoryCatalogAudit
from cys_core.infrastructure.catalog.audit_postgres import PostgresCatalogAudit
from cys_core.infrastructure.catalog.catalog_singletons import CatalogSingletons
from cys_core.infrastructure.catalog.catalog_write_gate import CatalogWriteGate
from cys_core.infrastructure.catalog.memory_mcp import InMemoryMcpServerCatalog
from cys_core.infrastructure.catalog.memory_plans import InMemoryPlanCatalog
from cys_core.infrastructure.catalog.memory_skills import InMemorySkillCatalog
from cys_core.infrastructure.catalog.memory_tools import InMemoryToolCatalog
from cys_core.infrastructure.catalog.postgres_registry import (
    PostgresMcpServerCatalog,
    PostgresPlanCatalog,
    PostgresSkillCatalog,
    PostgresToolCatalog,
)


def _use_postgres() -> bool:
    return get_use_dynamic_catalog() and not get_use_memory_fallback()


def get_skill_catalog():
    def factory():
        if _use_postgres():
            return PostgresSkillCatalog(get_postgres_url())
        return InMemorySkillCatalog()

    return CatalogSingletons.get("skill_catalog", factory)


def get_plan_catalog():
    def factory():
        if _use_postgres():
            return PostgresPlanCatalog(get_postgres_url())
        return InMemoryPlanCatalog()

    return CatalogSingletons.get("plan_catalog", factory)


def get_mcp_catalog():
    def factory():
        if _use_postgres():
            return PostgresMcpServerCatalog(get_postgres_url())
        return InMemoryMcpServerCatalog()

    return CatalogSingletons.get("mcp_catalog", factory)


def get_tool_catalog():
    def factory():
        if _use_postgres():
            return PostgresToolCatalog(get_postgres_url())
        return InMemoryToolCatalog()

    return CatalogSingletons.get("tool_catalog", factory)


def get_catalog_audit():
    def factory():
        if _use_postgres():
            return PostgresCatalogAudit(get_postgres_url())
        return InMemoryCatalogAudit()

    return CatalogSingletons.get("catalog_audit", factory)


def get_catalog_write_gate(*, reload=None):
    def factory():
        from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog, reload_agent_registry

        return CatalogWriteGate(
            agent_catalog=get_agent_catalog(),
            skill_catalog=get_skill_catalog(),
            plan_catalog=get_plan_catalog(),
            mcp_catalog=get_mcp_catalog(),
            tool_catalog=get_tool_catalog(),
            audit=get_catalog_audit(),
            reload=reload or reload_agent_registry,
        )

    return CatalogSingletons.get("catalog_write_gate", factory)


def reset_catalog_singletons() -> None:
    CatalogSingletons.reset()
