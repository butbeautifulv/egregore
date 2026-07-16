from __future__ import annotations

from cys_core.application.runs.plan_helpers import apply_plan_delta, format_todo_snapshot
from cys_core.domain.runs.plan_models import TodoStatus, WorkTodo


def test_format_todo_snapshot_empty():
    text = format_todo_snapshot([])
    assert "no steps yet" in text


def test_apply_plan_delta_merges_statuses():
    todos = [WorkTodo(id="1", content="gather logs", status=TodoStatus.PENDING)]
    delta = {"todos": [{"id": "1", "status": "done"}, {"id": "2", "content": "enrich ioc", "status": "pending"}]}
    merged = apply_plan_delta(todos, delta)
    assert len(merged) == 2
    by_id = {t.id: t for t in merged}
    assert by_id["1"].status == TodoStatus.DONE
    assert by_id["2"].content == "enrich ioc"


def test_apply_plan_delta_failed_status():
    todos = [WorkTodo(id="1", content="step", status=TodoStatus.IN_PROGRESS)]
    merged = apply_plan_delta(todos, {"todos": [{"id": "1", "status": "failed"}]})
    assert merged[0].status == TodoStatus.FAILED
