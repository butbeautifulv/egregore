from __future__ import annotations

from functools import lru_cache

from cys_core.registry.agents import get_agent_registry


class ResourceSource:
    def list_worker_personas(self, profile_id: str | None = None) -> list[str]:
        del profile_id
        return [agent.name for agent in get_agent_registry().by_workers()]


@lru_cache(maxsize=1)
def get_resource_source() -> ResourceSource:
    return ResourceSource()
