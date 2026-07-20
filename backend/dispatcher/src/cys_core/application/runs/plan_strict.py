from __future__ import annotations

from cys_core.application.runtime_config import get_egregore_strict_plan
from cys_core.domain.runs.plan_models import TodoStatus, WorkTodo


def plan_delta_allowed(*, strict: bool | None = None) -> bool:
    return not (strict if strict is not None else get_egregore_strict_plan())


def merge_plan_delta_with_policy(
    todos: list[WorkTodo],
    plan_delta: dict,
    *,
    strict: bool | None = None,
) -> list[WorkTodo]:
    if not plan_delta_allowed(strict=strict):
        return todos
    from cys_core.application.runs.plan_helpers import apply_plan_delta

    return apply_plan_delta(todos, plan_delta)


def has_failed_todos(todos: list[WorkTodo]) -> bool:
    return any(t.status == TodoStatus.FAILED for t in todos)
