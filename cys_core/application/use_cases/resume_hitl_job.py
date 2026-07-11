from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from cys_core.application.ports.agent_runner import AgentRunner
from cys_core.domain.workers.models import JobResumeRequest, WorkerJobStatus


class HitlJobStore(Protocol):
    def get(self, job_id: str) -> Any | None: ...
    def mark_failed(self, job_id: str) -> None: ...
    def mark_running(self, job_id: str) -> None: ...
    def mark_completed(self, job_id: str) -> None: ...


class ResumeHitlJobError(Exception):
    pass


class ResumeHitlJob:
    """Resume a worker job after L1 human-in-the-loop approval."""

    def __init__(
        self,
        *,
        job_store: HitlJobStore,
        runtime: AgentRunner,
        record_hitl_approval: Callable[..., Any],
        params_hash: Callable[[dict[str, Any]], str],
        record_approval_bypass: Callable[[str], None] | None = None,
    ) -> None:
        self.job_store = job_store
        self.runtime = runtime
        self.record_hitl_approval = record_hitl_approval
        self.params_hash = params_hash
        self.record_approval_bypass = record_approval_bypass or (lambda _reason: None)

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

        self.record_hitl_approval(
            actor=request.actor,
            tool=pending.tool_name,
            persona=pending.persona,
            job_id=job_id,
            decision=request.decision,
            tool_args=tool_args,
            approval_id=pending.approval_id,
        )
        store.mark_running(job_id)

        resume_payload = {"decision": request.decision, "approval_id": pending.approval_id}
        result = await self.runtime.aresume(record.persona, record.session_id, resume_payload)
        store.mark_completed(job_id)
        return {"job_id": job_id, "status": "resumed", "result": result}
