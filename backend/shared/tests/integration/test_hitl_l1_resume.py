from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.domain.workers.models import JobResumeRequest, PendingHitlAction, WorkerJobStatus
from interfaces.control_plane.job_store import JobStore
from interfaces.api.hitl_resume import HitlResumeError, resume_worker_job


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hitl_resume_rejects_forged_approval(monkeypatch):
    store = JobStore()
    store.pause_for_hitl(
        PendingHitlAction(
            job_id="job-bad",
            session_id="worker:soc:job-bad",
            persona="soc",
            tool_name="run_active_scan",
            tool_args={"target": "x"},
            risk_level="high",
            approval_id="appr-real",
        ),
        {"params_hash": "abc"},
    )
    container = MagicMock()
    container.get_job_store.return_value = store
    monkeypatch.setattr("interfaces.api.hitl_resume.get_container", lambda: container)
    with pytest.raises(HitlResumeError, match="approval_id"):
        await resume_worker_job(
            "job-bad",
            JobResumeRequest(decision="approve", approval_id="appr-forged", actor="user"),
        )
    assert store.get("job-bad").status == WorkerJobStatus.AWAITING_APPROVAL
