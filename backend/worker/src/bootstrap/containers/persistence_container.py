from __future__ import annotations

from typing import TYPE_CHECKING

from bootstrap.settings import Settings

if TYPE_CHECKING:
    # Forward-ref only, for the type hint below.
    from bootstrap.container import Container
    from cys_core.application.ports.bus import AgentTransportConnector
    from cys_core.application.ports.job_queue import JobQueueConnector
    from cys_core.application.ports.memory import EpisodicMemoryStore


class PersistenceContainer:
    """Owns queue/transport/persistence/memory store connectors shared by api
    and worker. Sandbox connector, LangGraph PersistenceContext (agent thread
    checkpointing), context summarizer, and reflexion store are worker-only
    (agent-execution concerns, cys_core.infrastructure.sandbox/cys_core.persistence/
    context.factory/reflexion.memory don't exist outside worker) — those live
    directly on worker's own Container now, not here. See
    docs/MSP_BACKLOG.md §0/§1.2 for why this generic container
    must not carry methods that only resolve inside one sibling package.
    """

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._bus_dedup_store = None
        self._workspace_store = None

    @property
    def settings(self) -> Settings:
        return self._container.settings

    def get_job_queue(self, persona: str | None = None) -> "JobQueueConnector":
        from cys_core.infrastructure.queue import get_job_queue

        return get_job_queue(persona=persona, settings=self.settings)

    def get_bus_transport(self) -> "AgentTransportConnector":
        from cys_core.infrastructure.bus_transport import get_bus_transport

        return get_bus_transport(settings=self.settings)

    def get_job_store(self):
        from interfaces.control_plane.job_store import get_job_store

        return get_job_store(self.settings)

    def get_bus_dedup_store(self):
        if self._bus_dedup_store is None:
            from cys_core.infrastructure.bus_dedup_store import get_bus_dedup_store

            self._bus_dedup_store = get_bus_dedup_store(
                redis_url=self.settings.redis_url,
                strict_redis=self.settings.strict_redis_queue,
            )
        return self._bus_dedup_store

    def get_episodic_memory_store(self) -> "EpisodicMemoryStore":
        from cys_core.infrastructure.memory.factory import get_episodic_memory_store

        return get_episodic_memory_store(self.settings)

    def get_memory_read_service(self):
        from cys_core.infrastructure.memory.factory import get_memory_read_service

        return get_memory_read_service(self.settings)

    def get_memory_write_service(self):
        from cys_core.infrastructure.memory.factory import get_memory_write_service

        return get_memory_write_service(self.settings)

    def get_attachment_store(self):
        from cys_core.infrastructure.runs.factory import get_attachment_store

        return get_attachment_store()

    def get_workspace_store(self):
        if self._workspace_store is not None:
            return self._workspace_store
        from cys_core.infrastructure.persistence_store_factory import resolve_persistence_store
        from cys_core.infrastructure.workspace.memory_store import InMemoryWorkspaceStore
        from cys_core.infrastructure.workspace.postgres_store import PostgresWorkspaceStore

        def _use_postgres(settings: Settings) -> bool:
            connector = settings.workspace_store_connector.lower()
            if connector == "memory":
                return False
            if connector == "postgres":
                return True
            return not settings.use_memory_fallback and settings.stage != "test"

        self._workspace_store = resolve_persistence_store(
            self.settings,
            connector=self.settings.workspace_store_connector,
            use_postgres=_use_postgres,
            postgres_factory=PostgresWorkspaceStore,
            memory_factory=InMemoryWorkspaceStore,
            fallback_label="workspace_store",
        )
        return self._workspace_store
