from __future__ import annotations

import threading

import psycopg

from cys_core.application.runtime_config import (
    get_postgres_url,
    get_use_dynamic_catalog,
    get_use_memory_fallback,
)
from cys_core.application.ports.agent_definitions import AgentDefinitionsLoaderPort
from cys_core.domain.agents.models import AgentDefinition
from cys_core.domain.catalog.models import AgentCatalogEntry
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.infrastructure.catalog.catalog_mapper import entry_to_definition
from cys_core.infrastructure.catalog.catalog_singletons import CatalogSingletons
from cys_core.infrastructure.catalog.memory import InMemoryAgentCatalog
from cys_core.infrastructure.catalog.schema import CATALOG_SCHEMA_SQL

_definitions_loader: AgentDefinitionsLoaderPort | None = None

_registry_cache: object | None = None
_catalog_version: int = 0
_bus_reload_callback: object | None = None
_registry_lock = threading.Lock()


def register_definitions_loader(loader: AgentDefinitionsLoaderPort) -> None:
    global _definitions_loader
    _definitions_loader = loader


def register_bus_reload_callback(callback) -> None:
    global _bus_reload_callback
    _bus_reload_callback = callback


def _default_definitions_loader() -> AgentDefinitionsLoaderPort:
    from bootstrap.agent_definitions_loader import get_default_agent_definitions_loader

    return get_default_agent_definitions_loader()


def _create_agent_catalog():
    if get_use_dynamic_catalog() and not get_use_memory_fallback():
        from cys_core.infrastructure.catalog.postgres import PostgresAgentCatalog

        return PostgresAgentCatalog(get_postgres_url())
    return InMemoryAgentCatalog()


def get_agent_catalog():
    return CatalogSingletons.get("agent_catalog", _create_agent_catalog)


def ensure_catalog_schema(conn: psycopg.Connection) -> None:
    conn.execute(CATALOG_SCHEMA_SQL)
    conn.commit()


def load_hybrid_registry(root=None):
    """DB/catalog override merged with filesystem definitions."""
    from cys_core.registry.agents import AgentRegistry

    global _registry_cache, _catalog_version
    if get_use_dynamic_catalog():
        loader = _definitions_loader or _default_definitions_loader()
        catalog = get_agent_catalog()
        fs_agents = loader.load(root)
        merged: dict[str, AgentDefinition] = {}
        for name, defn in fs_agents.items():
            merged[name] = defn
        for entry in catalog.list_agents(enabled_only=True):
            merged[entry.name] = entry_to_definition(entry)
        _registry_cache = AgentRegistry(merged)
        _catalog_version = max((catalog.get_version(DEFAULT_PROFILE_ID).version, 1))
        from cys_core.observability.metrics import metrics

        metrics.catalog_version.labels(profile_id=DEFAULT_PROFILE_ID).set(_catalog_version)
        for profile in catalog.list_profiles():
            version = catalog.get_version(profile.id)
            metrics.catalog_version.labels(profile_id=profile.id).set(version.version)
        return _registry_cache
    return AgentRegistry.load(root)


def reload_agent_registry():
    global _registry_cache, _catalog_version
    from cys_core.registry.agents import get_agent_registry
    from cys_core.registry.skill_registry import get_skill_registry

    get_agent_registry.cache_clear()
    get_skill_registry.cache_clear()
    _registry_cache = load_hybrid_registry()
    _catalog_version += 1
    from cys_core.observability.metrics import metrics

    metrics.catalog_version.labels(profile_id=DEFAULT_PROFILE_ID).set(_catalog_version)
    if _bus_reload_callback is not None:
        try:
            _bus_reload_callback(get_agent_registry())
        except Exception:
            pass
    return _registry_cache


def get_catalog_version_metric() -> int:
    return _catalog_version
