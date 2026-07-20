from __future__ import annotations

import pytest

from cys_core.domain.workers.models import PendingHitlAction, WorkerJobStatus
from interfaces.control_plane.job_store import JobStore


@pytest.mark.unit
def test_job_store_pause_and_pending_list():
    store = JobStore()
    store.upsert_running("job-1", "worker:soc:job-1", "soc")
    pending = PendingHitlAction(
        job_id="job-1",
        session_id="worker:soc:job-1",
        persona="soc",
        tool_name="run_active_scan",
        tool_args={"target": "example.com"},
        approval_id="appr-1",
    )
    store.pause_for_hitl(pending, {"tool": "run_active_scan"})
    record = store.get("job-1")
    assert record is not None
    assert record.status == WorkerJobStatus.AWAITING_APPROVAL
    assert len(store.list_pending_approvals()) == 1
