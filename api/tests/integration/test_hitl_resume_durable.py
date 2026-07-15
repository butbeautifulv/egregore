from __future__ import annotations

import pytest

from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus
from cys_core.infrastructure.job_store.factory import reset_job_store
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore


@pytest.mark.integration
def test_hitl_pause_survives_new_store_instance():
    """Simulate process restart: write via store A, read via fresh store B with shared backing."""
    backing = InMemoryJobStore()
    store_a = InMemoryJobStore()
    store_a._jobs = backing._jobs
    store_a.pause_for_hitl(
        PendingHitlAction(
            job_id="job-durable",
            session_id="worker:soc:job-durable",
            persona="soc",
            tool_name="run_active_scan",
            tool_args={"target": "example.com"},
            approval_id="appr-durable",
        ),
        {"tool": "run_active_scan"},
    )

    reset_job_store()
    store_b = InMemoryJobStore()
    store_b._jobs = backing._jobs
    record = store_b.get("job-durable")
    assert record is not None
    assert record.status == WorkerJobStatus.AWAITING_APPROVAL
    assert store_b.list_pending_approvals()[0].approval_id == "appr-durable"
