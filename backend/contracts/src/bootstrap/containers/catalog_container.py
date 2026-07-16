from __future__ import annotations

from typing import TYPE_CHECKING

from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog, reload_agent_registry
from cys_core.infrastructure.catalog.registry_factory import (
    get_catalog_audit,
    get_catalog_write_gate,
    get_mcp_catalog,
    get_plan_catalog,
    get_skill_catalog,
    get_tool_catalog,
)

if TYPE_CHECKING:
    # Forward-ref only: Container is api's or worker's own composition
    # root (whichever installs this sub-container), never a module inside
    # contracts itself.
    from bootstrap.container import Container  # ty: ignore[unresolved-import]


class CatalogContainer:
    """Owns catalog/registry ports and catalog seed/mutation services.

    get_tool_registry_port() is worker-only (cys_core.infrastructure.registry.
    tool_registry_adapter wraps the LangChain tool registry, worker-only per
    docs/MICROSERVICES_SPLIT_PLAN.md §1) — it lives directly on worker's own
    Container now, not here, so this shared container never reaches for a
    module that doesn't exist in api.
    """

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._agent_registry_port = None
        self._schema_registry_port = None
        self._persona_ranking_port = None
        self._skill_registry_port = None
        self._resource_source_port = None
        self._agents_root_port = None
        self._datasource_catalog_port = None
        self._datasource_audit_port = None
        self._policy_merge_port = None
        self._catalog_mutation_service = None
        self._product_pack_port = None
        self._catalog_seed_loaders_port = None
        self._policy_defaults_port = None
        self._application_settings_port = None

    @property
    def settings(self):
        return self._container.settings

    # -- bootstrap adapter ports (settings/config seeding) --

    def get_product_pack_port(self):
        if self._product_pack_port is None:
            from cys_core.infrastructure.bootstrap.product_pack_adapter import build_product_pack_port

            self._product_pack_port = build_product_pack_port()
        return self._product_pack_port

    def get_catalog_seed_loaders_port(self):
        if self._catalog_seed_loaders_port is None:
            from cys_core.infrastructure.bootstrap.catalog_seed_adapter import build_catalog_seed_loaders_port

            self._catalog_seed_loaders_port = build_catalog_seed_loaders_port()
        return self._catalog_seed_loaders_port

    def get_policy_defaults_port(self):
        if self._policy_defaults_port is None:
            from cys_core.infrastructure.bootstrap.policy_defaults_adapter import build_policy_defaults_port

            self._policy_defaults_port = build_policy_defaults_port()
        return self._policy_defaults_port

    def get_application_settings_port(self):
        if self._application_settings_port is None:
            from cys_core.infrastructure.bootstrap.application_settings_adapter import build_application_settings_port

            self._application_settings_port = build_application_settings_port()
        return self._application_settings_port

    # -- catalogs --

    def get_catalog_version(self) -> int:
        from cys_core.infrastructure.catalog.catalog_registry import get_catalog_version_metric

        return get_catalog_version_metric()

    def get_seed_catalog(self):
        from bootstrap.catalog_loader import load_profile_pack
        from cys_core.application.use_cases.seed_catalog import SeedCatalog
        from cys_core.infrastructure.catalog.tool_catalog_seed import load_tools_for_seed

        return SeedCatalog(
            self.get_agent_catalog(),
            tool_catalog=self.get_tool_catalog(),
            seed_loaders=self.get_catalog_seed_loaders_port(),
            load_profile_pack=load_profile_pack,
            load_tools_for_seed=load_tools_for_seed,
            reload=self.reload_catalog,
            mutation=self.get_catalog_mutation_service(),
        )

    def get_agent_catalog(self):
        return get_agent_catalog()

    def get_skill_catalog(self):
        return get_skill_catalog()

    def get_plan_catalog(self):
        return get_plan_catalog()

    def get_mcp_catalog(self):
        return get_mcp_catalog()

    def get_tool_catalog(self):
        return get_tool_catalog()

    def get_catalog_write_gate(self):
        return get_catalog_write_gate()

    def get_catalog_audit(self):
        return get_catalog_audit()

    def reload_catalog(self) -> None:
        reload_agent_registry()

    # -- registry ports --

    def get_agent_registry_port(self):
        if self._agent_registry_port is not None:
            return self._agent_registry_port
        from cys_core.infrastructure.registry.agent_registry_adapter import build_agent_registry_port

        self._agent_registry_port = build_agent_registry_port()
        return self._agent_registry_port

    def get_schema_registry_port(self):
        if self._schema_registry_port is not None:
            return self._schema_registry_port
        from cys_core.infrastructure.registry.schema_registry_adapter import build_schema_registry_port

        self._schema_registry_port = build_schema_registry_port()
        return self._schema_registry_port

    def get_persona_ranking_port(self):
        if self._persona_ranking_port is not None:
            return self._persona_ranking_port
        from cys_core.infrastructure.catalog.persona_ranking import build_persona_ranking_port

        self._persona_ranking_port = build_persona_ranking_port(
            catalog=self.get_agent_catalog(),
            policy_port=self._container.get_profile_policy_port(),
        )
        return self._persona_ranking_port

    def get_skill_registry_port(self):
        if self._skill_registry_port is not None:
            return self._skill_registry_port
        from cys_core.infrastructure.registry.skill_registry_adapter import build_skill_registry_port

        self._skill_registry_port = build_skill_registry_port()
        return self._skill_registry_port

    def get_resource_source_port(self):
        if self._resource_source_port is not None:
            return self._resource_source_port
        from cys_core.infrastructure.registry.resource_source_adapter import build_resource_source_port

        self._resource_source_port = build_resource_source_port(
            self.get_agent_registry_port(),
            agent_catalog=self.get_agent_catalog(),
        )
        return self._resource_source_port

    def get_agents_root_port(self):
        if self._agents_root_port is not None:
            return self._agents_root_port
        from cys_core.infrastructure.registry.agents_root_adapter import build_agents_root_port

        self._agents_root_port = build_agents_root_port()
        return self._agents_root_port

    def get_datasource_catalog_port(self):
        if self._datasource_catalog_port is not None:
            return self._datasource_catalog_port
        from cys_core.infrastructure.datasources.catalog_adapter import build_datasource_catalog_port

        self._datasource_catalog_port = build_datasource_catalog_port()
        return self._datasource_catalog_port

    def get_datasource_audit_port(self):
        if self._datasource_audit_port is not None:
            return self._datasource_audit_port
        from cys_core.infrastructure.datasources.audit_adapter import build_datasource_audit_port

        self._datasource_audit_port = build_datasource_audit_port()
        return self._datasource_audit_port

    def get_policy_merge_port(self):
        if self._policy_merge_port is not None:
            return self._policy_merge_port
        from cys_core.infrastructure.catalog.policy_merge_adapter import build_policy_merge_port

        self._policy_merge_port = build_policy_merge_port()
        return self._policy_merge_port

    def get_catalog_mutation_service(self):
        if self._catalog_mutation_service is not None:
            return self._catalog_mutation_service
        from cys_core.application.catalog_mutation_service import CatalogMutationService

        self._catalog_mutation_service = CatalogMutationService(
            write_gate=get_catalog_write_gate(reload=self.reload_catalog),
            agent_catalog=self.get_agent_catalog(),
            tool_catalog=self.get_tool_catalog(),
            audit=self.get_catalog_audit(),
            reload=self.reload_catalog,
        )
        return self._catalog_mutation_service
