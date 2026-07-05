from __future__ import annotations

from typing import Callable

from cys_core.application.ports.catalog import AgentCatalogPort
from cys_core.application.ports.schema_registry import SchemaRegistryPort
from cys_core.application.catalog_mutation_service import CatalogMutationService
from cys_core.domain.catalog.models import AgentCatalogEntry, CatalogSource, PersonaQuality


class UpsertCatalogAgent:
    def __init__(
        self,
        catalog: AgentCatalogPort,
        *,
        schema_registry: SchemaRegistryPort,
        reload: Callable[[], None] | None = None,
        write_gate=None,
        mutation: CatalogMutationService | None = None,
    ) -> None:
        self.catalog = catalog
        self.schema_registry = schema_registry
        self.reload = reload or (lambda: None)
        self._write_gate = write_gate
        self._mutation = mutation

    def execute(
        self,
        name: str,
        body: dict,
        *,
        actor: str = "api",
    ) -> AgentCatalogEntry:
        schema_name = body.get("output_schema")
        if schema_name:
            try:
                self.schema_registry.get(schema_name)
            except KeyError:
                from cys_core.application.runtime_config import get_use_dynamic_catalog

                if not get_use_dynamic_catalog():
                    raise
        existing = self.catalog.get_agent(name)
        entry = AgentCatalogEntry(
            name=name,
            description=body.get("description", ""),
            role=body.get("role", "worker"),
            output_schema=schema_name,
            tools=body.get("tools", []),
            skills=body.get("skills", []),
            capabilities=body.get("capabilities", existing.capabilities if existing else []),
            trust_level=body.get("trust_level", "internal"),
            bus_recipients=body.get("bus_recipients", []),
            enabled=body.get("enabled", True),
            profile_id=body.get("profile_id", "cybersec-soc"),
            system_prompt=body.get("system_prompt", existing.system_prompt if existing else ""),
            system_prompt_digest=existing.system_prompt_digest if existing else "",
            version_tag=body.get("version_tag", existing.version_tag if existing else ""),
            quality=existing.quality if existing else PersonaQuality(),
            source=CatalogSource.API,
            budget_max_tokens=body.get("budget_max_tokens", existing.budget_max_tokens if existing else None),
            budget_max_cost_usd=body.get("budget_max_cost_usd", existing.budget_max_cost_usd if existing else None),
            budget_max_tool_calls=body.get("budget_max_tool_calls", existing.budget_max_tool_calls if existing else None),
            data_clearance=body.get("data_clearance", existing.data_clearance if existing else "internal"),
        )
        if self._mutation is not None:
            saved = self._mutation.upsert_agent(entry, actor=actor)
        elif self._write_gate is not None:
            saved = self._write_gate.upsert_agent(entry, actor=actor)
        else:
            saved = self.catalog.upsert_agent(entry)
            self.reload()
        return saved
