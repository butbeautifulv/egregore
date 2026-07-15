from __future__ import annotations

from typing import Protocol

from cys_core.domain.runs.plan_models import WorkTodo


class WorkTodoStorePort(Protocol):
    def list_todos(self, tenant_id: str, context_id: str) -> list[WorkTodo]: ...

    def replace_todos(self, tenant_id: str, context_id: str, todos: list[WorkTodo]) -> None: ...
