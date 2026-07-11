from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.plan_follow_up import PlanFollowUpRunner
from cys_core.domain.engagement.models import Engagement, EngagementPlan, EngagementStatus
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


class _MetaPlanner:
    profile_id = "cybersec-soc"

    async def execute(self, _event: Any, *, profile_id: str) -> EngagementPlan:
        return EngagementPlan(
            personas=["soc", "intel"],
            sub_goals={"soc": "triage"},
            rationale="re-plan",
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
async def test_plan_follow_up_runner_enqueues_personas_and_publishes_started() -> None:
    store = MemoryEngagementStateStore()
    engagement = Engagement(
        id="wo-1",
        tenant_id="default",
        goal="closed investigation",
        status=EngagementStatus.CLOSED,
    )
    store.upsert(engagement)

    dispatch = MagicMock()
    dispatch.enqueuer.enqueue_from_routing = AsyncMock(return_value=["soc-job-1", "intel-job-1"])

    egress = MagicMock()
    runner = PlanFollowUpRunner(
        meta_planner=_MetaPlanner(),
        dispatch=dispatch,
        engagement_store=store,
        engagement_egress=egress,
    )
    job = WorkerJob(
        job_id="planner-fu-abc",
        event_id="e1",
        persona="planner",
        correlation_id="wo-1",
        tenant_id="default",
        payload={
            "phase": "follow_up",
            "work_kind": "follow_up_plan",
            "follow_up_id": "fu-test",
            "operator_message": "Re-run with new context",
        },
    )

    result = await runner.execute(job, "wo-1")

    assert result["job_ids"] == ["soc-job-1", "intel-job-1"]
    dispatch.enqueuer.enqueue_from_routing.assert_awaited_once()
    egress.publish_event.assert_called()
    started_call = next(
        call for call in egress.publish_event.call_args_list if call.args[1] == "follow_up_plan_started"
    )
    assert started_call.args[2]["follow_up_id"] == "fu-test"

    updated = store.get("default", "wo-1")
    assert updated is not None
    assert updated.status == EngagementStatus.ENQUEUED
    assert updated.active_follow_up_id == "fu-test"
