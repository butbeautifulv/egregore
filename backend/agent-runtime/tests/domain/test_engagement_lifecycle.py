from __future__ import annotations

import pytest

from cys_core.domain.engagement.models import Engagement, EngagementStatus


@pytest.mark.unit
def test_begin_planning_moves_created_to_planning() -> None:
    engagement = Engagement(id="e1", goal="investigate")
    engagement.begin_planning(goal="updated goal")
    assert engagement.status == EngagementStatus.PLANNING
    assert engagement.goal == "updated goal"
    assert engagement.planner_status == "planning"


@pytest.mark.unit
def test_mark_enqueued_sets_status_and_jobs() -> None:
    engagement = Engagement(id="e1", goal="g")
    engagement.mark_enqueued(["job-1", "job-2"])
    assert engagement.status == EngagementStatus.ENQUEUED
    assert engagement.job_ids == ["job-1", "job-2"]


@pytest.mark.unit
def test_record_persona_completed_closes_when_plan_done() -> None:
    engagement = Engagement(
        id="e1",
        goal="g",
        status=EngagementStatus.RUNNING,
        planner_plan=["soc", "network"],
        completed_personas=["soc"],
    )
    engagement.record_persona_completed("network")
    assert engagement.status == EngagementStatus.CLOSED
    assert engagement.completed_personas == ["soc", "network"]


@pytest.mark.unit
def test_fail_synthesis_degraded_closes_with_findings() -> None:
    from cys_core.domain.engagement.models import SynthesisStatus

    engagement = Engagement(
        id="e1",
        goal="g",
        status=EngagementStatus.RUNNING,
        planner_plan=["soc", "intel"],
        synthesis_persona="consultant",
        synthesis_status=SynthesisStatus.RUNNING,
        findings_summary=[{"persona": "soc", "job_id": "soc-j1", "finding": {"summary": "ok"}}],
        failed_personas=["soc"],
    )
    engagement.fail_synthesis("worker_job_timeout", degraded=True)
    assert engagement.status == EngagementStatus.CLOSED
    assert "soc" in engagement.completed_personas
    assert engagement.final_report is not None
    assert engagement.final_report.get("degraded") is True
