from __future__ import annotations

from typing import Any

from cys_core.application.use_cases.resume_hitl_job import ResumeHitlJob, ResumeHitlJobError
from cys_core.domain.workers.models import JobResumeRequest
from cys_core.observability.metrics import metrics
from cys_core.runtime.agent import get_runtime
from interfaces.control_plane.job_store import get_job_store
from interfaces.gateways.tool.approval import params_hash, record_hitl_approval

HitlResumeError = ResumeHitlJobError


async def resume_worker_job(job_id: str, request: JobResumeRequest) -> dict[str, Any]:
    use_case = ResumeHitlJob(
        job_store=get_job_store(),
        runtime=get_runtime(),
        record_hitl_approval=record_hitl_approval,
        params_hash=params_hash,
        record_approval_bypass=metrics.record_approval_bypass,
    )
    return await use_case.execute(job_id, request)
