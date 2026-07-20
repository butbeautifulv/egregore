from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.workers.follow_up_publisher import FollowUpAnswerPublisher
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.domain.engagement.models import Engagement, EngagementStatus
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus


def _follow_up_job(*, work_kind: str = "follow_up_qa") -> WorkerJob:
    return WorkerJob(
        job_id="consultant-fu-abc",
        persona="consultant",
        tenant_id="default",
        event_id="eng-1",
        correlation_id="eng-1",
        payload={
            "phase": "follow_up",
            "work_kind": work_kind,
            "follow_up_id": "fu-1",
            "operator_message": "why?",
        },
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finalize_failure_publishes_follow_up_failed_sse() -> None:
    egress = MagicMock()
    publisher = FollowUpAnswerPublisher(engagement_egress=egress)
    enqueue_next = AsyncMock()
    fin = WorkerJobFinalizer(
        job_store=MagicMock(),
        queue=MagicMock(),
        bus=MagicMock(),
        agent_catalog=MagicMock(),
        engagement_egress=egress,
        enqueue_next_planned_persona=MagicMock(execute=enqueue_next),
        follow_up_publisher=publisher,
    )
    fin._queue.send_to_dlq = AsyncMock()
    job = _follow_up_job()

    await fin.finalize_failure(job, error_string="empty_finding")

    failed = [c for c in egress.publish_event.call_args_list if c.args[1] == "follow_up_failed"]
    assert len(failed) == 1
    assert failed[0].args[2]["follow_up_id"] == "fu-1"
    enqueue_next.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_child_success_does_not_close_engagement() -> None:
    store = MagicMock()
    engagement = Engagement(
        id="eng-1",
        tenant_id="default",
        goal="done",
        status=EngagementStatus.CLOSED,
    )
    store.get.return_value = engagement
    fin = WorkerJobFinalizer(
        job_store=MagicMock(),
        queue=MagicMock(),
        bus=MagicMock(),
        agent_catalog=MagicMock(),
        engagement_store=store,
        engagement_egress=MagicMock(),
    )
    job = WorkerJob(
        job_id="soc-fu-child",
        persona="soc",
        tenant_id="default",
        event_id="eng-1",
        correlation_id="eng-1",
        payload={"phase": "follow_up", "work_kind": "follow_up_child"},
    )
    job.transition_to(WorkerJobStatus.RUNNING)

    await fin.mark_success(job, "eng-1")

    assert engagement.status == EngagementStatus.CLOSED
    store.upsert.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_success_closes_engagement() -> None:
    store = MagicMock()
    engagement = Engagement(
        id="eng-1",
        tenant_id="default",
        goal="done",
        status=EngagementStatus.RUNNING,
        follow_up_spawned_job_ids=["soc-fu-child"],
    )
    store.get.return_value = engagement
    fin = WorkerJobFinalizer(
        job_store=MagicMock(),
        queue=MagicMock(),
        bus=MagicMock(),
        agent_catalog=MagicMock(),
        engagement_store=store,
        engagement_egress=MagicMock(),
    )
    job = _follow_up_job(work_kind="follow_up_orchestrate")
    job.transition_to(WorkerJobStatus.RUNNING)

    await fin.mark_follow_up_success(job, "eng-1")

    assert engagement.status == EngagementStatus.CLOSED
    assert engagement.follow_up_spawned_job_ids == []
    store.upsert.assert_called_once()
    assert job.status == WorkerJobStatus.COMPLETED
