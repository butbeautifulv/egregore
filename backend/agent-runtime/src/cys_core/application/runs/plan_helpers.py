from __future__ import annotations

from typing import Any

from cys_core.domain.runs.plan_models import TodoStatus, WorkTodo

_VALID_STATUSES = {s.value for s in TodoStatus}


def format_todo_snapshot(todos: list[WorkTodo]) -> str:
    """Render persisted todos for injection into each conductor turn (todo.md style)."""
    if not todos:
        return "Plan progress (todo.md): no steps yet. Emit plan_delta with numbered todos."
    lines = ["Plan progress (todo.md):"]
    for index, todo in enumerate(todos, start=1):
        note = f" — assigned: {todo.assigned_persona}" if todo.assigned_persona else ""
        lines.append(f"{index}. {todo.status.value.upper()} — {todo.content}{note}")
    lines.append(
        "Update every turn: set plan_delta.todos with id, content, status "
        "(pending|in_progress|done|failed|cancelled), and optional note."
    )
    return "\n".join(lines)


def _normalize_status(raw: str) -> str:
    value = raw.lower().strip()
    if value == "failed":
        return TodoStatus.FAILED.value
    return value if value in _VALID_STATUSES else TodoStatus.PENDING.value


def apply_plan_delta(todos: list[WorkTodo], plan_delta: dict[str, Any]) -> list[WorkTodo]:
    """Merge conductor plan_delta into persisted todos."""
    if not plan_delta:
        return todos
    updates = plan_delta.get("todos") or plan_delta.get("steps") or []
    if not isinstance(updates, list) or not updates:
        return todos
    by_id = {t.id: t.model_copy() for t in todos}
    for index, item in enumerate(updates):
        if not isinstance(item, dict):
            continue
        todo_id = str(item.get("id") or item.get("step") or index + 1)
        content = str(item.get("content") or item.get("title") or item.get("description") or "")
        status_raw = str(item.get("status") or TodoStatus.PENDING.value)
        status = _normalize_status(status_raw)
        assigned = str(item.get("assigned_persona") or item.get("persona") or "")
        if todo_id in by_id:
            existing = by_id[todo_id]
            by_id[todo_id] = existing.model_copy(
                update={
                    "content": content or existing.content,
                    "status": TodoStatus(status),
                    "assigned_persona": assigned or existing.assigned_persona,
                }
            )
        elif content:
            by_id[todo_id] = WorkTodo(
                id=todo_id,
                content=content,
                status=TodoStatus(status),
                assigned_persona=assigned,
            )
    return list(by_id.values())
