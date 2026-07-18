from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

from cys_core.domain.workers.models import JobResumeRequest, WorkerJob, WorkerJobStatus

logger = structlog.get_logger(__name__)


class HitlJobStore(Protocol):
    def get(self, job_id: str) -> Any | None: ...
    def mark_failed(self, job_id: str) -> None: ...
    def mark_running(self, job_id: str) -> None: ...
    def mark_completed(self, job_id: str) -> None: ...


class HitlJobQueue(Protocol):
    async def aenqueue(self, job: WorkerJob) -> str: ...


class ResumeHitlJobError(Exception):
    pass


class ResumeHitlJob:
    """Resume a worker job after L1 human-in-the-loop approval.

    Does not execute the continuation itself — enqueues a new WorkerJob
    (resume_checkpoint_ref pointing at the interrupted LangGraph thread) for
    a worker to pick up through the normal Dispatcher -> ExecutionBackend
    path, with the same budget/sandbox/tool-gateway policy as any other job.
    Previously this called runtime.aresume() directly, inline, in the HTTP
    request handler — the exact action a human had to approve *because it's
    high-risk* ran with none of those guarantees applied (Discovery B,
    docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md).
    """

    def __init__(
        self,
        *,
        job_store: HitlJobStore,
        job_queue_factory: Callable[[str], HitlJobQueue],
        record_hitl_approval: Callable[..., Any],
        params_hash: Callable[[dict[str, Any]], str],
        record_approval_bypass: Callable[[str], None] | None = None,
        record_hitl_approval_blocking: Callable[..., Awaitable[tuple[Any, bool]]] | None = None,
        audit_failclosed_mode: str = "off",
    ) -> None:
        """``job_queue_factory(persona) -> queue`` rather than a fixed queue
        instance — the resume job's persona isn't known until the interrupted
        job's record is read inside execute(), and queues are persona-scoped
        (WorkerOrchestrator/get_job_queue follow the same pattern).

        ``record_hitl_approval_blocking``/``audit_failclosed_mode``: §10.3/§41 — when the
        mode is 'shadow' or 'enforce', the approve/edit decision awaits the real Kafka
        audit-trail publish outcome instead of firing-and-forgetting it. In 'enforce' mode a
        failed publish blocks the action (ResumeHitlJobError) rather than letting a high-risk
        action proceed on nothing but a background warning log. Defaults to 'off' (unchanged,
        fire-and-forget) so existing callers that don't pass these two params keep today's
        behavior exactly.
        """
        self.job_store = job_store
        self.job_queue_factory = job_queue_factory
        self.record_hitl_approval = record_hitl_approval
        self.params_hash = params_hash
        self.record_approval_bypass = record_approval_bypass or (lambda _reason: None)
        self.record_hitl_approval_blocking = record_hitl_approval_blocking
        self.audit_failclosed_mode = audit_failclosed_mode

    async def execute(self, job_id: str, request: JobResumeRequest) -> dict[str, Any]:
        store = self.job_store
        record = store.get(job_id)
        if record is None:
            raise ResumeHitlJobError(f"Unknown job: {job_id}")
        if record.status != WorkerJobStatus.AWAITING_APPROVAL or record.pending_hitl is None:
            raise ResumeHitlJobError(f"Job {job_id} is not awaiting approval")

        pending = record.pending_hitl
        if request.approval_id and request.approval_id != pending.approval_id:
            self.record_approval_bypass("invalid_approval_id")
            raise ResumeHitlJobError("Invalid approval_id for high-risk action")

        if request.decision == "reject":
            self.record_hitl_approval(
                actor=request.actor,
                tool=pending.tool_name,
                persona=pending.persona,
                job_id=job_id,
                decision="reject",
                tool_args=pending.tool_args,
                approval_id=pending.approval_id,
            )
            store.mark_failed(job_id)
            return {"job_id": job_id, "status": "rejected"}

        tool_args = request.edited_args if request.decision == "edit" and request.edited_args else pending.tool_args
        if request.decision == "approve":
            expected_hash = record.hitl_preview.get("params_hash", "")
            if expected_hash and self.params_hash(tool_args) != expected_hash:
                self.record_approval_bypass("params_hash_mismatch")
                raise ResumeHitlJobError("Tool args hash mismatch — approval bypass blocked")

        if self.audit_failclosed_mode in {"shadow", "enforce"} and self.record_hitl_approval_blocking is not None:
            _record, published = await self.record_hitl_approval_blocking(
                actor=request.actor,
                tool=pending.tool_name,
                persona=pending.persona,
                job_id=job_id,
                decision=request.decision,
                tool_args=tool_args,
                approval_id=pending.approval_id,
            )
            if not published:
                if self.audit_failclosed_mode == "enforce":
                    self.record_approval_bypass("hitl_audit_publish_failed")
                    raise ResumeHitlJobError(
                        "HITL approval audit trail publish failed — action blocked"
                    )
                logger.warning(
                    "hitl_audit_publish_failed_shadow",
                    job_id=job_id,
                    approval_id=pending.approval_id,
                )
                self.record_approval_bypass("hitl_audit_publish_failed_shadow")
        else:
            self.record_hitl_approval(
                actor=request.actor,
                tool=pending.tool_name,
                persona=pending.persona,
                job_id=job_id,
                decision=request.decision,
                tool_args=tool_args,
                approval_id=pending.approval_id,
            )
        # Takes the original job_id out of AWAITING_APPROVAL (so it stops
        # showing up in /approvals/pending) — the resume job below tracks its
        # own, separate lifecycle in job_store under resume_job_id.
        store.mark_running(job_id)

        resume_job_id = f"resume-{job_id}"
        resume_job = WorkerJob(
            job_id=resume_job_id,
            event_id=job_id,
            persona=record.persona,
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            resume_checkpoint_ref=record.session_id,
            payload={
                "decision": request.decision,
                "approval_id": pending.approval_id,
                "tool_name": pending.tool_name,
                "tool_args": tool_args,
            },
        )
        await self.job_queue_factory(record.persona).aenqueue(resume_job)
        return {"job_id": job_id, "resume_job_id": resume_job_id, "status": "resume_submitted"}
