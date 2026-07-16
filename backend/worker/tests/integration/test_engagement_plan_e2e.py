from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.run_engagement_planner import EngagementPlannerRunner
from cys_core.domain.engagement.models import Engagement, EngagementPlan, EngagementStatus
from cys_core.domain.engagement.planner_job import ENGAGEMENT_PLAN_WORK_KIND, ENGAGEMENT_PLANNER_PERSONA
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


class _MetaPlanner:
    profile_id = "cybersec-soc"

    async def execute(self, _event: Any, *, profile_id: str) -> EngagementPlan:
        return EngagementPlan(
            personas=["soc", "network"],
            sub_goals={"soc": "triage", "network": "beaconing"},
            rationale="initial plan",
            synthesis_persona="coordinator",
        )

    def to_worker_jobs_payload(self, plan: EngagementPlan) -> dict[str, Any]:
        return {
            "personas": list(plan.personas),
            "sub_goals": dict(plan.sub_goals),
            "depends_on": dict(plan.depends_on),
            "rationale": plan.rationale,
        }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_engagement_planner_runner_enqueues_personas_and_marks_enqueued() -> None:
    store = MemoryEngagementStateStore()
    engagement = Engagement(
        id="eng-1",
        tenant_id="default",
        goal="Investigate beaconing",
        status=EngagementStatus.PLANNING,
        planner_status="planning",
    )
    store.upsert(engagement)

    dispatch = MagicMock()
    dispatch.enqueuer.enqueue_from_routing = AsyncMock(return_value=["soc-job-1", "network-job-1"])

    egress = MagicMock()
    runner = EngagementPlannerRunner(
        meta_planner=_MetaPlanner(),
        dispatch=dispatch,
        engagement_store=store,
        engagement_egress=egress,
    )
    job = WorkerJob(
        job_id="planner-abc",
        event_id="eng-1",
        persona=ENGAGEMENT_PLANNER_PERSONA,
        correlation_id="eng-1",
        tenant_id="default",
        payload={
            "goal": "Investigate beaconing",
            "message": "Investigate beaconing",
            "profile_id": "cybersec-soc",
            "plan_strategy": "meta_llm",
            "work_kind": ENGAGEMENT_PLAN_WORK_KIND,
        },
    )

    result = await runner.execute(job, "eng-1")

    assert result["job_ids"] == ["soc-job-1", "network-job-1"]
    dispatch.enqueuer.enqueue_from_routing.assert_awaited_once()
    call_args = dispatch.enqueuer.enqueue_from_routing.call_args
    assert call_args.args[1] == ["soc", "network"]
    # Regression: job.payload's "work_kind": "engagement_plan" must not leak
    # into the specialist jobs this plan spawns — they are regular "soc"/
    # "network" jobs, not engagement-plan jobs themselves.
    assert "work_kind" not in call_args.kwargs["payload"]
    egress.publish_status.assert_any_call(
        "eng-1",
        "enqueued",
        {
            "tenant_id": "default",
            "job_ids": ["soc-job-1", "network-job-1"],
            "personas": ["soc", "network"],
        },
    )

    updated = store.get("default", "eng-1")
    assert updated is not None
    assert updated.status == EngagementStatus.ENQUEUED
    assert updated.job_ids == ["soc-job-1", "network-job-1"]
