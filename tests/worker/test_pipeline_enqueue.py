from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.enqueue_next_planned_persona import EnqueueNextPlannedPersona
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from cys_core.infrastructure.queue import InMemoryJobQueue


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_next_planned_persona_after_soc_success() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="inv-pipe",
            tenant_id="default",
            goal="investigate ip",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc", "intel", "hunter"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            job_ids=[
                "soc-inv-pipe-aaa",
                "intel-inv-pipe-bbb",
                "hunter-inv-pipe-ccc",
            ],
            completed_personas=["soc"],
        )
    )
    queue = InMemoryJobQueue()
    egress = MagicMock()
    use_case = EnqueueNextPlannedPersona(
        engagement_store=store,
        queue=queue,
        engagement_egress=egress,
    )
    soc_job = WorkerJob(
        job_id="soc-inv-pipe-aaa",
        event_id="evt-pipe",
        persona="soc",
        correlation_id="inv-pipe",
        payload={"goal": "investigate ip", "planner_plan": ["soc", "intel", "hunter"]},
    )

    job_id = await use_case.execute(soc_job)

    assert job_id == "intel-inv-pipe-bbb"
    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "intel"
    egress.publish_status.assert_called_once()
    assert egress.publish_status.call_args.args[1] == "job_enqueued"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_runtime_failure_enqueues_next_persona() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="inv-fail-pipe",
            tenant_id="default",
            goal="investigate ip",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc", "intel"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            job_ids=["soc-inv-fail-pipe-aaa", "intel-inv-fail-pipe-bbb"],
            completed_personas=["soc"],
        )
    )
    queue = InMemoryJobQueue()
    enqueue_next = EnqueueNextPlannedPersona(engagement_store=store, queue=queue)
    finalizer = WorkerJobFinalizer(
        job_store=MagicMock(mark_failed=MagicMock()),
        queue=queue,
        bus=MagicMock(record_agent_failure=MagicMock()),
        agent_catalog=MagicMock(get_agent=MagicMock(return_value=None)),
        engagement_store=store,
        enqueue_next_planned_persona=enqueue_next,
    )
    soc_job = WorkerJob(
        job_id="soc-inv-fail-pipe-aaa",
        event_id="evt-fail",
        persona="soc",
        correlation_id="inv-fail-pipe",
        payload={"goal": "investigate ip"},
    )
    soc_job.transition_to(WorkerJobStatus.RUNNING)

    await finalizer.mark_runtime_failure(soc_job, "empty_finding")

    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "intel"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_success_enqueues_next_persona() -> None:
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="inv-finalizer",
            tenant_id="default",
            goal="investigate ip",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["soc", "intel"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            job_ids=["soc-inv-finalizer-aaa", "intel-inv-finalizer-bbb"],
            completed_personas=["soc"],
        )
    )
    queue = InMemoryJobQueue()
    enqueue_next = EnqueueNextPlannedPersona(engagement_store=store, queue=queue)
    finalizer = WorkerJobFinalizer(
        job_store=MagicMock(mark_completed=MagicMock()),
        queue=queue,
        bus=MagicMock(),
        agent_catalog=MagicMock(get_agent=MagicMock(return_value=None)),
        engagement_store=store,
        enqueue_next_planned_persona=enqueue_next,
    )
    soc_job = WorkerJob(
        job_id="soc-inv-finalizer-aaa",
        event_id="evt-finalizer",
        persona="soc",
        correlation_id="inv-finalizer",
        payload={"goal": "investigate ip"},
    )
    soc_job.transition_to(WorkerJobStatus.RUNNING)

    await finalizer.mark_success(soc_job, "inv-finalizer")

    assert len(queue._queue) == 1
    assert queue._queue[0].persona == "intel"
