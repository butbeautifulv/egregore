from __future__ import annotations

from typing import Any

from bootstrap.container import get_container
from cys_core.application.use_cases.resume_hitl_job import ResumeHitlJob, ResumeHitlJobError
from cys_core.domain.workers.models import JobResumeRequest
from cys_core.observability.metrics import metrics
from interfaces.gateways.tool.approval import (
    params_hash,
    record_hitl_approval,
    record_hitl_approval_blocking,
)

HitlResumeError = ResumeHitlJobError


async def resume_worker_job(job_id: str, request: JobResumeRequest) -> dict[str, Any]:
    container = get_container()
    store = container.get_job_store()
    record = store.get(job_id)
    pending_approval_id = record.pending_hitl.approval_id if record and record.pending_hitl else ""
    correlation_id = record.correlation_id if record else ""

    use_case = ResumeHitlJob(
        job_store=store,
        job_queue_factory=lambda persona: container.get_job_queue(persona=persona),
        record_hitl_approval=record_hitl_approval,
        params_hash=params_hash,
        record_approval_bypass=metrics.record_approval_bypass,
        record_hitl_approval_blocking=record_hitl_approval_blocking,
        audit_failclosed_mode=container.settings.hitl_audit_failclosed_mode,
    )
    result = await use_case.execute(job_id, request)

    container.publish_hitl_resolved(
        correlation_id=correlation_id,
        job_id=job_id,
        approval_id=request.approval_id or pending_approval_id,
        decision=request.decision,
        actor=request.actor or "operator",
    )
    return result
