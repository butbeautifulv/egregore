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
    enqueue = AsyncMock(return_value="consultant-eng-reconcile-synth")
    reconciler = ReconcileStuckEngagements(
        engagement_store=store,
        job_store=job_store,
        enqueue_synthesis_job=enqueue,
    )

    stats = await reconciler.execute()
    assert stats["synthesis_enqueued"] == 1
    enqueue.execute.assert_called_once()
    anchor: WorkerJob = enqueue.execute.call_args.args[0]
    assert anchor.persona == "soc"
