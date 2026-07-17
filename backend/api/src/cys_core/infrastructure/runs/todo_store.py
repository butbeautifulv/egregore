from __future__ import annotations

import threading

from cys_core.domain.runs.plan_models import WorkTodo


class InMemoryWorkTodoStore:
    def __init__(self) -> None:
        self._todos: dict[tuple[str, str], list[WorkTodo]] = {}
        self._lock = threading.Lock()

    def list_todos(self, tenant_id: str, context_id: str) -> list[WorkTodo]:
        with self._lock:
            return list(self._todos.get((tenant_id, context_id), []))

    def replace_todos(self, tenant_id: str, context_id: str, todos: list[WorkTodo]) -> None:
        with self._lock:
            self._todos[(tenant_id, context_id)] = list(todos)
