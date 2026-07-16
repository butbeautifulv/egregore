from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.workers.finding_publisher import should_publish_finding_to_bus
from cys_core.domain.follow_up.models import is_follow_up_plan_planner_job
from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
def test_follow_up_planner_job_is_plan_planner() -> None:
    job = WorkerJob(
        job_id="planner-fu-abc",
        event_id="e1",
        persona="planner",
        correlation_id="wo-1",
        payload={"work_kind": "follow_up_plan", "follow_up_id": "fu-1"},
    )
    assert is_follow_up_plan_planner_job(job.payload, persona=job.persona) is True


@pytest.mark.unit
def test_planner_worker_skips_bus_publish_guard() -> None:
    assert should_publish_finding_to_bus(persona="planner", role="control") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_worker_job_plan_follow_up_does_not_publish_finding() -> None:
    from cys_core.application.use_cases.run_worker_job import RunWorkerJob

    job = WorkerJob(
        job_id="planner-fu-abc",
        event_id="e1",
        persona="planner",
        correlation_id="wo-1",
        tenant_id="default",
        payload={
            "phase": "follow_up",
            "work_kind": "follow_up_plan",
            "follow_up_id": "fu-1",
            "operator_message": "Plan AD hardening",
        },
    )
    plan_runner = MagicMock()
    plan_runner.execute = AsyncMock(return_value={"job_ids": ["identity-1"], "summary": "ok"})
    finding_publisher = MagicMock()
    finding_publisher.publish = AsyncMock()
    job_finalizer = MagicMock()
    job_finalizer.mark_running = MagicMock()
    job_finalizer.publish_job_started = MagicMock()
    job_finalizer.mark_success = AsyncMock()

    runner = RunWorkerJob(
        context_builder=MagicMock(investigation_id=lambda _j: "wo-1"),
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
        plan_follow_up_runner=plan_runner,
    )

    result = await runner.execute(job, job, "worker:planner:planner-fu-abc", {"status": "pending"})

    assert result.success is True
    plan_runner.execute.assert_awaited_once()
    finding_publisher.publish.assert_not_awaited()
