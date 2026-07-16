from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from cys_core.application.use_cases.resume_hitl_job import HitlJobQueue, HitlJobStore, ResumeHitlJob, ResumeHitlJobError
from cys_core.domain.workers.models import JobResumeRequest, PendingHitlAction, WorkerJobStatus
from interfaces.control_plane.job_store import JobStore


def _use_case(store: Any, fake_queue: Any) -> ResumeHitlJob:
    # JobStore (test-only) proxies to InMemoryJobStore via __getattr__, which
    # ty can't see structurally — same for the SimpleNamespace fake queue.
    # Both genuinely satisfy the protocols at runtime.
    return ResumeHitlJob(
        job_store=cast(HitlJobStore, store),
        job_queue_factory=lambda persona: cast(HitlJobQueue, fake_queue),
        record_hitl_approval=lambda **kwargs: None,
        params_hash=lambda args: "irrelevant",
    )


def _pending(job_id: str = "job-1") -> PendingHitlAction:
    return PendingHitlAction(
        job_id=job_id,
        session_id=f"worker:soc:{job_id}",
        persona="soc",
        tool_name="run_active_scan",
        tool_args={"target": "lab"},
        approval_id="appr-1",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resume_enqueues_job_with_checkpoint_ref_instead_of_running_inline():
    """Discovery B: approving a HITL action must not execute the continuation
    inline in the API process — it must go through the same queue/Dispatcher
    path as any other job."""
    store = JobStore()
    pending = _pending()
    store.pause_for_hitl(pending, {"params_hash": "irrelevant"})

    fake_queue = SimpleNamespace(aenqueue=AsyncMock(return_value="resume-job-1"))
    use_case = _use_case(store, fake_queue)

    out = await use_case.execute("job-1", JobResumeRequest(decision="approve", approval_id="appr-1", actor="alice"))

    assert out["status"] == "resume_submitted"
    assert out["resume_job_id"] == "resume-job-1"
    fake_queue.aenqueue.assert_awaited_once()
    enqueued_job = fake_queue.aenqueue.await_args.args[0]
    assert enqueued_job.resume_checkpoint_ref == "worker:soc:job-1"
    assert enqueued_job.persona == "soc"
    assert enqueued_job.payload["decision"] == "approve"
    assert enqueued_job.payload["approval_id"] == "appr-1"
    # Original job leaves AWAITING_APPROVAL (no longer shows up in
    # /approvals/pending) even though nothing executed it yet.
    assert store.get("job-1").status == WorkerJobStatus.RUNNING


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resume_rejects_without_enqueueing():
    store = JobStore()
    store.pause_for_hitl(_pending("job-2"), {"params_hash": "irrelevant"})
    fake_queue = SimpleNamespace(aenqueue=AsyncMock())
    use_case = _use_case(store, fake_queue)

    out = await use_case.execute("job-2", JobResumeRequest(decision="reject", approval_id="appr-1", actor="alice"))

    assert out["status"] == "rejected"
    fake_queue.aenqueue.assert_not_called()
    assert store.get("job-2").status == WorkerJobStatus.FAILED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resume_bad_approval_id_raises_before_enqueueing():
    store = JobStore()
    store.pause_for_hitl(_pending("job-3"), {"params_hash": "irrelevant"})
    fake_queue = SimpleNamespace(aenqueue=AsyncMock())
    use_case = _use_case(store, fake_queue)

    with pytest.raises(ResumeHitlJobError):
        await use_case.execute(
            "job-3", JobResumeRequest(decision="approve", approval_id="wrong", actor="attacker")
        )
    fake_queue.aenqueue.assert_not_called()
