from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from bootstrap.settings import Settings, get_settings

if TYPE_CHECKING:
    from cys_core.application.ports import PersistenceContext
    from cys_core.application.ports.bus import AgentTransportConnector
    from cys_core.application.ports.job_queue import JobQueueConnector
    from cys_core.application.ports.memory import EpisodicMemoryStore, InvestigationStateStore
    from cys_core.application.ports.sandbox import SandboxConnector


class Container:
    """Composition root for infrastructure connectors and cross-layer wiring."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_job_queue(self, persona: str | None = None) -> JobQueueConnector:
        from cys_core.infrastructure.queue import get_job_queue

        return get_job_queue(persona=persona, settings=self.settings)

    def get_bus_transport(self) -> AgentTransportConnector:
        from cys_core.infrastructure.bus_transport import get_bus_transport

        return get_bus_transport(settings=self.settings)

    def get_sandbox_connector(self) -> SandboxConnector:
        from cys_core.infrastructure.sandbox import get_sandbox_connector

        return get_sandbox_connector(settings=self.settings)

    def get_persistence_context(self) -> PersistenceContext:
        from cys_core.persistence import get_persistence_connector

        return get_persistence_connector(self.settings.persistence_connector).open()

    async def get_async_persistence_context(self) -> PersistenceContext:
        from cys_core.persistence import get_persistence_connector

        connector = get_persistence_connector(self.settings.persistence_connector)
        return await connector.open_async()

    def get_job_store(self):
        from interfaces.control_plane.job_store import get_job_store

        return get_job_store(self.settings)

    def get_episodic_memory_store(self) -> EpisodicMemoryStore:
        from cys_core.infrastructure.memory.factory import get_episodic_memory_store

        return get_episodic_memory_store(settings=self.settings)

    def get_investigation_state_store(self) -> InvestigationStateStore:
        from cys_core.infrastructure.memory.factory import get_investigation_state_store

        return get_investigation_state_store(settings=self.settings)

    def get_token_verifier(self):
        from cys_core.infrastructure.auth.factory import build_token_verifier

        return build_token_verifier(self.settings)

    def wire_hitl_pause(self) -> None:
        from cys_core.infrastructure.kafka_paused import publish_paused_job_sync
        from cys_core.middleware import hitl_pause
        from cys_core.observability.metrics import metrics
        store = self.get_job_store()

        class _JobStoreHitlAdapter:
            def pause_for_hitl(self, pending: Any, preview: dict[str, Any]) -> None:
                store.pause_for_hitl(pending, preview)

            def list_pending_approvals(self) -> list[Any]:
                return store.list_pending_approvals()

        hitl_pause.configure(
            registry=_JobStoreHitlAdapter(),
            publish_paused=publish_paused_job_sync,
            on_pause_count=lambda count: metrics.refresh_hitl_pending(count),
        )

    def wire_tool_backend(self) -> None:
        from cys_core.registry.tools import configure_tool_backend
        from interfaces.gateways.tool.adapters.rag import rag_query_tool
        from interfaces.gateways.tool.adapters.siem import query_siem_readonly_search

        class _GatewayToolBackend:
            def query_siem(self, query: str, time_range: str = "24h") -> dict[str, Any]:
                return query_siem_readonly_search(query=query, time_range=time_range)

            def rag_query(self, query: str, persona: str = "soc", tenant: str = "default") -> dict[str, Any]:
                return rag_query_tool(query=query, persona=persona, tenant=tenant)

        configure_tool_backend(_GatewayToolBackend())


@lru_cache
def get_container() -> Container:
    container = Container()
    container.wire_hitl_pause()
    container.wire_tool_backend()
    return container
