from __future__ import annotations

from cys_core.application.ports.reflexion import ReflexionLesson, ReflexionStorePort
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.domain.security.exceptions import SecurityViolation


class InMemoryReflexionStore:
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


def _sanitize_lesson(text: str) -> str:
    sanitizer = get_input_sanitizer()
    try:
        return sanitizer.sanitize(text, source="reflexion")
    except SecurityViolation:
        return "[reflexion lesson removed by sanitizer]"


_store = InMemoryReflexionStore()


def get_reflexion_store() -> ReflexionStorePort:
    return _store
