from __future__ import annotations

import pytest

from cys_core.domain.runs.plan_models import (
    ClarifyingQuestion,
    PlanApproval,
    TodoStatus,
    WorkPlan,
    WorkTodo,
)


@pytest.mark.unit
def test_work_todo_defaults():
    todo = WorkTodo(id="t1", content="triage alerts")
    assert todo.status == TodoStatus.PENDING
    assert todo.assigned_persona == ""


@pytest.mark.unit
def test_work_plan_with_questions_and_workers():
    plan = WorkPlan(
        questions=[ClarifyingQuestion(id="q1", question="Which host?")],
        todos=[WorkTodo(id="t1", content="enrich IOC")],
        proposed_workers=["soc", "network"],
        rationale="initial plan",
        awaiting_user_input=True,
    )
    assert len(plan.questions) == 1
    assert plan.proposed_workers == ["soc", "network"]


@pytest.mark.unit
def test_plan_approval_edit():
    approval = PlanApproval(decision="edit", edited_plan=WorkPlan(rationale="edited"))
    assert approval.decision == "edit"
    assert approval.edited_plan is not None
