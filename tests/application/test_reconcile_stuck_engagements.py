from __future__ import annotations

import pytest

from cys_core.domain.engagement.models import Engagement, EngagementStatus, SynthesisStatus
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


@pytest.mark.unit
def test_append_finding_dedup_by_persona_job_id() -> None:
    store = MemoryEngagementStateStore()
    engagement = Engagement(id="eng-dedup", tenant_id="default", goal="g")
    store.upsert(engagement)

    finding = {"persona": "soc", "job_id": "soc-j1", "finding": {"summary": "a"}}
    store.append_finding("default", "eng-dedup", finding)
    store.append_finding("default", "eng-dedup", finding)

    updated = store.get("default", "eng-dedup")
    assert updated is not None
    assert len(updated.findings_summary) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_enqueues_pending_synthesis() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from cys_core.application.use_cases.reconcile_stuck_engagements import ReconcileStuckEngagements
    from cys_core.domain.workers.models import WorkerJob

    store = MemoryEngagementStateStore()
    engagement = Engagement(
        id="eng-reconcile",
        tenant_id="default",
        goal="g",
        status=EngagementStatus.RUNNING,
        planner_plan=["soc", "intel"],
        completed_personas=["soc"],
        failed_personas=["intel"],
        synthesis_status=SynthesisStatus.PENDING,
        job_ids=["soc-eng-reconcile-abc"],
        findings_summary=[{"persona": "soc", "job_id": "soc-eng-reconcile-abc", "finding": {"summary": "ok"}}],
    )
    store.upsert(engagement)

    job_store = MagicMock()
    job_store.get.return_value = MagicMock(persona="soc")
    job_store.list_active_bus_jobs.return_value = []
    job_store.list_stale_bus_jobs.return_value = []
    enqueue = AsyncMock(return_value="consultant-eng-reconcile-synth")
    reconciler = ReconcileStuckEngagements(
        engagement_store=store,
        job_store=job_store,
        enqueue_synthesis_job=enqueue,
        synthesis_stale_multiplier=2.0,
        default_job_timeout_s=300.0,
        synth_job_timeout_s=180.0,
        planner_timeout_seconds=120,
        scan_limit=50,
    )

    stats = await reconciler.execute()
    assert stats["synthesis_enqueued"] == 1
    enqueue.execute.assert_called_once()
    anchor: WorkerJob = enqueue.execute.call_args.args[0]
    assert anchor.persona == "soc"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_fails_stale_bus_jobs_before_synthesis() -> None:
    from datetime import timedelta
    from unittest.mock import AsyncMock, MagicMock

    from cys_core.application.use_cases.enqueue_synthesis_job import EnqueueSynthesisJob
    from cys_core.application.use_cases.reconcile_stuck_engagements import ReconcileStuckEngagements
    from cys_core.domain.workers.models import WorkerJobStatus
    from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore
    from cys_core.infrastructure.queue import InMemoryJobQueue

    store = MemoryEngagementStateStore()
    engagement = Engagement(
        id="eng-bus-reconcile",
        tenant_id="default",
        goal="g",
        status=EngagementStatus.RUNNING,
        planner_plan=["soc", "intel"],
        synthesis_persona="consultant",
        completed_personas=["soc", "intel"],
        failed_personas=[],
        synthesis_status=SynthesisStatus.PENDING,
        job_ids=["soc-eng-bus-reconcile-abc", "intel-eng-bus-reconcile-def", "soc-bus-stale"],
        findings_summary=[
            {"persona": "soc", "job_id": "soc-eng-bus-reconcile-abc", "finding": {"summary": "ok"}},
            {"persona": "intel", "job_id": "intel-eng-bus-reconcile-def", "finding": {"summary": "ok"}},
        ],
    )
    store.upsert(engagement)

    job_store = InMemoryJobStore()
    job_store.upsert_running(
        "soc-bus-stale",
        "worker:soc:soc-bus-stale",
        "soc",
        correlation_id="eng-bus-reconcile",
    )
    job_store._updated_at["soc-bus-stale"] = job_store._updated_at["soc-bus-stale"] - timedelta(seconds=600)

    queue = InMemoryJobQueue()
    synth = EnqueueSynthesisJob(engagement_store=store, queue=queue, job_store=job_store)
    reconciler = ReconcileStuckEngagements(
        engagement_store=store,
        job_store=job_store,
        enqueue_synthesis_job=synth,
        default_job_timeout_s=300.0,
        synth_job_timeout_s=180.0,
        planner_timeout_seconds=120,
        synthesis_stale_multiplier=2.0,
        scan_limit=50,
    )

    stats = await reconciler.execute()
    assert stats["stale_failed"] == 1
    assert stats["synthesis_enqueued"] == 1
    assert job_store.get("soc-bus-stale").status == WorkerJobStatus.FAILED
    assert any(job.job_id.endswith("-synth") for job in queue._queue)
