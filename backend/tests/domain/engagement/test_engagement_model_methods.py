from __future__ import annotations

import pytest

from cys_core.domain.engagement.models import (
    Engagement,
    EngagementPlan,
    EngagementStatus,
    ExecutionMode,
    PlanStrategy,
    SynthesisStatus,
)


def _engagement(**kwargs) -> Engagement:
    defaults = {"id": "eng-1", "goal": "investigate alert"}
    defaults.update(kwargs)
    return Engagement(**defaults)


@pytest.mark.unit
def test_engagement_status_is_terminal() -> None:
    assert EngagementStatus.CLOSED.is_terminal() is True
    assert EngagementStatus.FAILED.is_terminal() is True
    assert EngagementStatus.RUNNING.is_terminal() is False


@pytest.mark.unit
def test_engagement_plan_effective_execution_mode() -> None:
    assert EngagementPlan(personas=["soc"]).effective_execution_mode() == ExecutionMode.PARALLEL
    assert EngagementPlan(personas=["soc", "intel"]).effective_execution_mode() == ExecutionMode.STAGED
    assert (
        EngagementPlan(personas=["soc"], execution_mode=ExecutionMode.PARALLEL).effective_execution_mode()
        == ExecutionMode.PARALLEL
    )


@pytest.mark.unit
def test_reopen_and_close_follow_up_lifecycle() -> None:
    engagement = _engagement(status=EngagementStatus.CLOSED, active_follow_up_id="fu-1")
    engagement.reopen_for_follow_up()
    assert engagement.status == EngagementStatus.RUNNING
    engagement.close_after_follow_up()
    assert engagement.status == EngagementStatus.CLOSED
    assert engagement.active_follow_up_id is None


@pytest.mark.unit
def test_close_after_initial_qa_skips_synthesis() -> None:
    engagement = _engagement(active_follow_up_id="fu-2", synthesis_status=SynthesisStatus.PENDING)
    engagement.close_after_initial_qa()
    assert engagement.status == EngagementStatus.CLOSED
    assert engagement.synthesis_status == SynthesisStatus.SKIPPED


@pytest.mark.unit
def test_begin_follow_up_planning_records_history() -> None:
    engagement = _engagement(
        status=EngagementStatus.CLOSED,
        planner_plan=["soc", "intel"],
        planner_rationale="initial",
        follow_up_iteration=0,
        follow_up_goal="",
        completed_personas=["soc", "intel", "consultant"],
        failed_personas=["network"],
        synthesis_persona="consultant",
    )
    engagement.begin_follow_up_planning(operator_message="  drill deeper  ", follow_up_id="fu-3")
    assert engagement.status == EngagementStatus.PLANNING
    assert engagement.follow_up_iteration == 1
    assert engagement.follow_up_goal == "drill deeper"
    assert engagement.active_follow_up_id == "fu-3"
    assert engagement.planner_status == "planning"
    assert engagement.completed_personas == ["consultant"]
    assert engagement.failed_personas == []
    assert len(engagement.plan_history) == 1


@pytest.mark.unit
def test_begin_planning_keeps_non_created_status() -> None:
    engagement = _engagement(status=EngagementStatus.RUNNING)
    engagement.begin_planning()
    assert engagement.status == EngagementStatus.RUNNING
    assert engagement.planner_status == "planning"


@pytest.mark.unit
def test_mark_enqueued_empty_jobs_stays_planning() -> None:
    engagement = _engagement(status=EngagementStatus.PLANNING)
    engagement.mark_enqueued([])
    assert engagement.status == EngagementStatus.PLANNING


@pytest.mark.unit
def test_specialists_terminal_and_maybe_close_blocked_by_synthesis() -> None:
    engagement = _engagement(
        status=EngagementStatus.RUNNING,
        planner_plan=["soc"],
        completed_personas=["soc"],
        synthesis_status=SynthesisStatus.PENDING,
    )
    assert engagement.specialists_terminal() is True
    engagement.record_persona_completed("soc")
    assert engagement.status == EngagementStatus.RUNNING


@pytest.mark.unit
def test_record_persona_completed_skips_synthesis_persona() -> None:
    engagement = _engagement(
        status=EngagementStatus.RUNNING,
        planner_plan=["soc", "consultant"],
        synthesis_persona="consultant",
        completed_personas=["soc"],
    )
    engagement.record_persona_completed("consultant")
    assert "consultant" not in engagement.completed_personas


@pytest.mark.unit
def test_record_persona_failed_moves_between_lists() -> None:
    engagement = _engagement(
        status=EngagementStatus.RUNNING,
        planner_plan=["soc", "intel"],
        completed_personas=["soc"],
    )
    engagement.record_persona_failed("soc")
    assert "soc" not in engagement.completed_personas
    assert "soc" in engagement.failed_personas
    engagement.record_persona_failed("intel", plan_personas=["soc", "intel"])
    assert engagement.status == EngagementStatus.CLOSED


@pytest.mark.unit
def test_complete_synthesis_reconciles_findings() -> None:
    engagement = _engagement(
        status=EngagementStatus.RUNNING,
        synthesis_persona="consultant",
        findings_summary=[{"persona": "soc"}, {"persona": "consultant"}],
        failed_personas=["soc"],
    )
    engagement.complete_synthesis({"summary": "done"})
    assert engagement.status == EngagementStatus.CLOSED
    assert "soc" in engagement.completed_personas


@pytest.mark.unit
def test_fail_synthesis_non_degraded_marks_failed() -> None:
    engagement = _engagement(status=EngagementStatus.RUNNING, synthesis_persona="consultant")
    engagement.fail_synthesis("planner error", degraded=False)
    assert engagement.status == EngagementStatus.FAILED


@pytest.mark.unit
def test_apply_planner_result_sets_synthesis_and_sub_goals() -> None:
    engagement = _engagement(status=EngagementStatus.CREATED, goal="old")
    engagement.apply_planner_result(
        ["soc", "consultant"],
        status="ready",
        rationale="because",
        goal="new goal",
        execution_mode=ExecutionMode.STAGED,
        synthesis_persona="consultant",
        planner_sub_goals={"soc": "triage"},
        planner_depends_on={"intel": ["soc"]},
    )
    assert engagement.planner_plan == ["soc", "consultant"]
    assert engagement.goal == "new goal"
    assert engagement.synthesis_status == SynthesisStatus.SKIPPED
    assert engagement.planner_sub_goals == {"soc": "triage"}
    assert engagement.planner_depends_on == {"intel": ["soc"]}
    assert engagement.status == EngagementStatus.PLANNING


@pytest.mark.unit
def test_apply_planner_result_skips_synthesis_when_in_plan() -> None:
    engagement = _engagement()
    engagement.apply_planner_result(["soc", "consultant"], status="ready", synthesis_persona="consultant")
    assert engagement.synthesis_status == SynthesisStatus.SKIPPED


@pytest.mark.unit
def test_fail_guardrail() -> None:
    engagement = _engagement(status=EngagementStatus.RUNNING)
    engagement.fail_guardrail("bus guard tripped")
    assert engagement.status == EngagementStatus.FAILED
    assert engagement.planner_error == "bus guard tripped"
    assert engagement.planner_status == "failed"


@pytest.mark.unit
def test_engagement_request_plan_strategy_default() -> None:
    from cys_core.domain.engagement.models import EngagementRequest

    assert EngagementRequest(goal="g").plan_strategy == PlanStrategy.META_LLM
