from __future__ import annotations

from typing import Any, Protocol

from cys_core.domain.memory.models import InvestigationState, MemoryEntry, MemoryScope


class EpisodicMemoryStore(Protocol):
    def append(self, entry: MemoryEntry) -> None: ...

    def query(self, scope: MemoryScope, *, limit: int = 20) -> list[MemoryEntry]: ...

    def search_by_investigation(
        self, tenant_id: str, investigation_id: str, *, limit: int = 20
    ) -> list[MemoryEntry]: ...

    def list_by_tenant(
        self, tenant_id: str, *, limit: int = 100, agent: str | None = None
    ) -> list[MemoryEntry]: ...


class InvestigationStateStore(Protocol):
    """Deprecated: use ``EngagementStateStore`` instead."""
    def get(self, tenant_id: str, investigation_id: str) -> InvestigationState | None: ...

    def upsert(self, state: InvestigationState) -> None: ...

    def append_finding(self, tenant_id: str, investigation_id: str, finding: dict[str, Any]) -> None: ...

    def mark_persona_done(self, tenant_id: str, investigation_id: str, persona: str) -> None: ...

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[InvestigationState]: ...
