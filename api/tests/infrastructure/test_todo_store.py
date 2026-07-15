from __future__ import annotations

import pytest

from cys_core.domain.runs.plan_models import WorkTodo
from cys_core.infrastructure.runs.todo_store import InMemoryWorkTodoStore


@pytest.mark.unit
def test_todo_store_replace_and_list():
    store = InMemoryWorkTodoStore()
    todos = [WorkTodo(id="1", content="a", status="pending")]
    store.replace_todos("default", "ctx-1", todos)
    assert store.list_todos("default", "ctx-1")[0].content == "a"
