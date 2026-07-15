from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.enqueue_follow_up import EnqueueFollowUp
from cys_core.application.workers.follow_up_aggregator import FollowUpAggregator
from cys_core.domain.engagement.models import Engagement, EngagementStatus, SynthesisStatus
from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.domain.workers.models import WorkerJobStatus
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore


def _closed_engagement() -> Engagement:
    return Engagement(
        id="eng-closed",
        tenant_id="default",
        goal="done",
        status=EngagementStatus.CLOSED,
        synthesis_status=SynthesisStatus.DONE,
        follow_up_spawn_count=2,
        follow_up_spawned_job_ids=["soc-fu-old"],
    )


@pytest.mark.unit
def test_orchestrate_enqueue_resets_spawn_state() -> None:
    episodic = InMemoryEpisodicMemoryStore()
    memory_writer = MemoryWriteService(episodic)
    memory_reader = MemoryReadService(episodic)
    engagement = _closed_engagement()
    engagement_store = MagicMock()
    engagement_store.get.return_value = engagement
    job_store = MagicMock()
    job_store.list_by_investigation.return_value = []
    use_case = EnqueueFollowUp(
        engagement_store=engagement_store,
        memory_writer=memory_writer,
        memory_reader=memory_reader,
        job_store=job_store,
        queue=MagicMock(),
    )

    result = use_case.execute(
        tenant_id="default",
        engagement_id="eng-closed",
        message="reinvestigate lateral movement",
        mode="orchestrate",
    )

    assert result["work_kind"] == "follow_up_orchestrate"
    assert engagement.follow_up_spawn_count == 0
    assert engagement.follow_up_spawned_job_ids == []


@pytest.mark.unit
def test_aggregator_reads_spawned_children_from_engagement() -> None:
    store = MagicMock()
    engagement = Engagement(
        id="eng-1",
        tenant_id="default",
        goal="done",
        follow_up_spawned_job_ids=["soc-fu-a", "intel-fu-b"],
    )
    store.get.return_value = engagement
    aggregator = FollowUpAggregator(
        MagicMock(),
        engagement_store=store,
        timeout_s=300.0,
        poll_s=2.0,
    )

    child_ids = aggregator.spawned_child_ids("default", "eng-1", orchestrator_job_id="conductor-fu-x")

    assert child_ids == ["soc-fu-a", "intel-fu-b"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_children_offloads_blocking_job_store_reads() -> None:
    """job_store.get() is a blocking psycopg call under the Postgres backend.

    wait_for_children() polls it in a loop for up to timeout_s; if that call
    ran directly on the event loop (instead of via asyncio.to_thread, as
    fixed in follow_up_aggregator.py), every other coroutine scheduled on the
    loop would be starved for the duration of each poll's DB round-trip. This
    mirrors the WorkerJobFinalizer sync-psycopg-in-async-def bug that was
    already fixed in job_finalizer.py.
    """

    job_store = MagicMock()

    def blocking_get(job_id: str) -> MagicMock:
        time.sleep(0.2)  # simulate a slow synchronous DB round-trip
        record = MagicMock()
        record.status = WorkerJobStatus.COMPLETED
        return record

    job_store.get.side_effect = blocking_get

    aggregator = FollowUpAggregator(job_store, timeout_s=5.0, poll_s=0.05)

    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        for _ in range(20):
            await asyncio.sleep(0.02)
            ticks += 1

    ticker_task = asyncio.create_task(ticker())
    result = await aggregator.wait_for_children(["job-a", "job-b"])
    ticks_during_wait = ticks
    ticker_task.cancel()

    assert result is True
    # job_store.get() is called once per child job (two here), each taking
    # 0.2s. If those calls ran synchronously on the event loop instead of via
    # asyncio.to_thread, the ticker task would never get scheduled until
    # wait_for_children returned, so ticks_during_wait would be 0 (verified
    # by temporarily reproducing the pre-fix code path against this same
    # test). With the fix, the blocking reads run in worker threads and the
    # ticker keeps making progress concurrently.
    assert ticks_during_wait >= 3
