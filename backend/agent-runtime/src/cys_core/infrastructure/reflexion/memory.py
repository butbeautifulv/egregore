from __future__ import annotations

from cys_core.application.ports.memory import EpisodicMemoryStore
from cys_core.application.ports.reflexion import ReflexionLesson, ReflexionStorePort
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer

# Generous but bounded over-fetch: EpisodicMemoryStore.search_by_investigation has no
# memory_type filter, so a straight limit=N read could be starved by "finding"/"conversation"
# entries for the same investigation and silently return fewer than N real lessons even
# when N exist. Filtering client-side after a wider fetch is correct (never drops a real
# lesson) at the cost of some extra rows read — acceptable for a per-investigation lesson
# list that's inherently small. docs/MSP_BACKLOG.md §9/§38.
_FETCH_MULTIPLIER = 8
_FETCH_CAP = 200


class InMemoryReflexionStore:
    """Process-local fallback — used directly only when no EpisodicMemoryStore is available
    (e.g. import-time default before bootstrap.container wires the real one in)."""

    def __init__(self) -> None:
        self._items: list[ReflexionLesson] = []

    def append(self, lesson: ReflexionLesson) -> None:
        safe = _sanitize_lesson(lesson.lesson)
        self._items.append(lesson.model_copy(update={"lesson": safe}))

    def list_for_investigation(self, tenant_id: str, investigation_id: str, *, limit: int = 5) -> list[str]:
        hits = [
            item.lesson
            for item in reversed(self._items)
            if item.tenant_id == tenant_id and item.investigation_id == investigation_id
        ]
        return hits[:limit]


class EpisodicReflexionStore:
    """Adapts ReflexionStorePort onto the existing EpisodicMemoryStore (memory_type="lesson")
    instead of a separate process-local list — reuses its already-tested Postgres backend,
    connect-with-retry (§32), and memory-fallback wiring rather than duplicating a new table
    and a new "restart loses everything" gap right next to the one this closes.
    docs/MSP_BACKLOG.md §9's audit found reflexion lessons were the one
    memory_type declared in the schema but never actually persisted anywhere durable."""

    def __init__(self, episodic_store: EpisodicMemoryStore) -> None:
        self._episodic = episodic_store

    def append(self, lesson: ReflexionLesson) -> None:
        from cys_core.domain.memory.models import MemoryEntry, MemoryScope

        safe = _sanitize_lesson(lesson.lesson)
        self._episodic.append(
            MemoryEntry(
                scope=MemoryScope(tenant_id=lesson.tenant_id, investigation_id=lesson.investigation_id),
                content=safe,
                memory_type="lesson",
                source_agent=lesson.source,
            )
        )

    def list_for_investigation(self, tenant_id: str, investigation_id: str, *, limit: int = 5) -> list[str]:
        fetch_limit = min(_FETCH_CAP, max(limit * _FETCH_MULTIPLIER, limit))
        entries = self._episodic.search_by_investigation(tenant_id, investigation_id, limit=fetch_limit)
        lessons = [entry.content for entry in entries if entry.memory_type == "lesson"]
        return lessons[:limit]


def _sanitize_lesson(text: str) -> str:
    sanitizer = get_input_sanitizer()
    try:
        return sanitizer.sanitize(text, source="reflexion")
    except SecurityViolation:
        return "[reflexion lesson removed by sanitizer]"


_store: ReflexionStorePort | None = None


def configure_reflexion_store(store: ReflexionStorePort) -> None:
    global _store
    _store = store


def get_reflexion_store() -> ReflexionStorePort:
    global _store
    if _store is None:
        _store = InMemoryReflexionStore()
    return _store
