from __future__ import annotations

import json

import pytest

from cys_core.application.workers.context_builder import WorkerContextBuilder
from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


@pytest.mark.unit
def test_job_input_includes_goal_sub_goal_and_planner_plan() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="inv-ctx",
            tenant_id="default",
            goal="Investigate IP 10.8.182.2",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
        )
    )
    builder = WorkerContextBuilder(engagement_store=store)
    job = WorkerJob(
        job_id="soc-inv-ctx-aaa",
        event_id="evt-ctx",
        persona="soc",
        correlation_id="inv-ctx",
        payload={
            "goal": "Investigate IP 10.8.182.2",
            "planner_plan": ["soc", "intel", "hunter"],
            "sub_goals": {"soc": "Triage alerts for 10.8.182.2"},
        },
    )

    parsed = json.loads(builder.job_input(job))

    assert parsed["persona"] == "soc"
    assert parsed["goal"] == "Investigate IP 10.8.182.2"
    assert parsed["sub_goal"] == "Triage alerts for 10.8.182.2"
    assert parsed["planner_plan"] == ["soc", "intel", "hunter"]
