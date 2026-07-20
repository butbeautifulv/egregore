from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.domain.engagement.planner_job import (
    ENGAGEMENT_PLAN_WORK_KIND,
    ENGAGEMENT_PLANNER_PERSONA,
    is_engagement_plan_job,
)
from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
def test_engagement_plan_job_is_recognized() -> None:
    job = WorkerJob(
        job_id="planner-abc",
        event_id="eng-1",
        persona=ENGAGEMENT_PLANNER_PERSONA,
        correlation_id="eng-1",
        payload={"work_kind": ENGAGEMENT_PLAN_WORK_KIND},
    )
    assert is_engagement_plan_job(job.payload, persona=job.persona) is True


@pytest.mark.unit
def test_follow_up_plan_job_is_not_engagement_plan_job() -> None:
    job = WorkerJob(
        job_id="planner-fu-abc",
        event_id="e1",
        persona="planner",
        correlation_id="wo-1",
        payload={"work_kind": "follow_up_plan"},
    )
    assert is_engagement_plan_job(job.payload, persona=job.persona) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_worker_job_routes_engagement_plan_to_planner_runner() -> None:
    from cys_core.application.use_cases.run_worker_job import RunWorkerJob

    job = WorkerJob(
        job_id="planner-abc",
        event_id="eng-1",
        persona=ENGAGEMENT_PLANNER_PERSONA,
        correlation_id="eng-1",
        tenant_id="default",
        payload={
            "goal": "Investigate beaconing",
            "work_kind": ENGAGEMENT_PLAN_WORK_KIND,
        },
    )
    planner_runner = MagicMock()
    planner_runner.execute = AsyncMock(return_value={"job_ids": ["soc-1", "network-1"], "summary": "ok"})
    finding_publisher = MagicMock()
    finding_publisher.publish = AsyncMock()
    job_finalizer = MagicMock()
    job_finalizer.mark_running = MagicMock()
    job_finalizer.publish_job_started = MagicMock()
    job_finalizer.mark_success = AsyncMock()

    runner = RunWorkerJob(
        context_builder=MagicMock(investigation_id=lambda _j: "eng-1"),
        agent_executor=MagicMock(),
        result_validator=MagicMock(),
        finding_publisher=finding_publisher,
        job_finalizer=job_finalizer,
        registry=MagicMock(),
        sandbox=MagicMock(),
        sanitizer=MagicMock(),
        worker_tracing=MagicMock(),
        use_tool_gateway=False,
        resolve_mcp_tools=MagicMock(),
        resolve_legacy_tools=MagicMock(),
        make_load_skill_tool=MagicMock(),
        engagement_planner_runner=planner_runner,
    )

    result = await runner.execute(job, job, "worker:planner:planner-abc", {"status": "pending"})

    assert result.success is True
    planner_runner.execute.assert_awaited_once()
    finding_publisher.publish.assert_not_awaited()
