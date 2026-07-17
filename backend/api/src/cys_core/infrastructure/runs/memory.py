from __future__ import annotations

import threading

from cys_core.domain.runs.state_models import RunState


class InMemoryRunStateStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str, str], RunState] = {}
        self._lock = threading.Lock()

    def _key(self, tenant_id: str, context_id: str, kind: str) -> tuple[str, str, str]:
        return tenant_id, context_id, kind

    def get(self, tenant_id: str, context_id: str, kind: str) -> RunState | None:
        with self._lock:
            return self._states.get(self._key(tenant_id, context_id, kind))

    def upsert(self, state: RunState) -> None:
        ctx = state.run_context
        with self._lock:
            self._states[self._key(ctx.tenant_id, ctx.context_id, ctx.kind.value)] = state

    def list_recent(self, tenant_id: str, *, limit: int = 20) -> list[RunState]:
        with self._lock:
            items = [state for state in self._states.values() if state.run_context.tenant_id == tenant_id]
        return items[:limit]
