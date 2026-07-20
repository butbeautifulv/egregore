from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.use_cases.enqueue_next_planned_persona import EnqueueNextPlannedPersona
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.domain.engagement.models import (
    Engagement,
    EngagementMode,
    EngagementStatus,
    ExecutionMode,
    PlanStrategy,
)
from cys_core.domain.engagement.planner_job import ENGAGEMENT_PLAN_WORK_KIND, ENGAGEMENT_PLANNER_PERSONA
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore
from cys_core.infrastructure.queue import InMemoryJobQueue


def _planner_job(investigation_id: str) -> WorkerJob:
    job = WorkerJob(
        job_id=f"planner-{investigation_id}",
        event_id=investigation_id,
        persona=ENGAGEMENT_PLANNER_PERSONA,
        correlation_id=investigation_id,
        tenant_id="default",
        payload={"goal": "investigate", "work_kind": ENGAGEMENT_PLAN_WORK_KIND},
    )
    job.transition_to(WorkerJobStatus.RUNNING)
    return job


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_success_does_not_duplicate_enqueue_first_staged_persona() -> None:
    """Regression test: EngagementPlannerRunner already enqueues the plan's own
    jobs (honoring pipeline_staged), so RunWorkerJob's later mark_success(planner_job)
    call must not also trigger EnqueueNextPlannedPersona — before the fix this
    double-enqueued the first staged persona's job for any STAGED-mode plan.
    """
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="eng-staged",
            tenant_id="default",
            goal="investigate",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.ENQUEUED,
            planner_plan=["soc", "intel"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
            execution_mode=ExecutionMode.STAGED,
            # Mirrors what EngagementPlannerRunner already did: only the first
            # staged persona's job actually reached the queue.
            job_ids=["soc-eng-staged-aaa"],
        )
    )
    queue = InMemoryJobQueue()
    enqueue_next = EnqueueNextPlannedPersona(engagement_store=store, queue=queue)

    fin = WorkerJobFinalizer(
        job_store=MagicMock(),
        queue=queue,
        bus=MagicMock(),
        agent_catalog=MagicMock(),
        engagement_store=store,
        enqueue_next_planned_persona=enqueue_next,
    )

    await fin.mark_success(_planner_job("eng-staged"), "eng-staged")

    assert len(queue._queue) == 0, "planner job's own mark_success must not re-enqueue 'soc'"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finalize_failure_does_not_pollute_failed_personas_with_planner() -> None:
    """Regression test: a failed engagement_plan job must not call
    mark_persona_failed(job) — "planner" is never a member of
    engagement.planner_plan, so this would incorrectly add it to
    engagement.failed_personas.
    """
    store = MemoryEngagementStateStore()
    store.upsert(
        Engagement(
            id="eng-fail",
            tenant_id="default",
            goal="investigate",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.PLANNING,
            plan_strategy=PlanStrategy.META_LLM,
        )
    )
    queue = MagicMock()
    queue.send_to_dlq = AsyncMock()
    fin = WorkerJobFinalizer(
        job_store=MagicMock(),
        queue=queue,
        bus=MagicMock(),
        agent_catalog=MagicMock(),
        engagement_store=store,
    )

    await fin.finalize_failure(_planner_job("eng-fail"), error_string="queue_unavailable")

    engagement = store.get("default", "eng-fail")
    assert engagement is not None
    assert ENGAGEMENT_PLANNER_PERSONA not in engagement.failed_personas
