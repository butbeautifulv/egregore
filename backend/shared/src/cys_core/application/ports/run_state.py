from __future__ import annotations

from typing import Protocol

from cys_core.domain.runs.state_models import RunState


class RunStateStorePort(Protocol):
    def get(self, tenant_id: str, context_id: str, kind: str) -> RunState | None: ...

    def upsert(self, state: RunState) -> None: ...

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[RunState]: ...
