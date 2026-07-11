from __future__ import annotations

import json
from typing import Any

from cys_core.application.engagement_streaming import publish_assistant_snapshot
from cys_core.application.ports.engagement_egress import EngagementEgressPort
from cys_core.application.ports.engagement_store import EngagementStateStore
from cys_core.domain.findings.quality_gates import coerce_consultant_advisory_result
from cys_core.domain.memory.services import MemoryWriteService
from cys_core.domain.workers.models import WorkerJob

_STRUCTURED_FINDING_KEYS = frozenset(
    {
        "topic",
        "summary",
        "finding",
        "recommendations",
        "recommended_actions",
        "references",
        "evidence",
        "risk_level",
        "analysis",
        "message",
        "personas",
        "sub_goals",
    }
)


def _is_structured_finding(result: dict[str, Any]) -> bool:
    if "error" in result:
        return False
    return any(key in result and result.get(key) not in (None, "", []) for key in _STRUCTURED_FINDING_KEYS)


def _content_type_for(result: dict[str, Any]) -> str:
    if isinstance(result.get("personas"), list) or isinstance(result.get("sub_goals"), dict):
        return "plan"
    if _is_structured_finding(result):
        return "finding"
    return "markdown"


def prepare_follow_up_result(job: WorkerJob, result: dict[str, Any]) -> dict[str, Any]:
    """Normalize follow-up worker output for persistence and SSE."""
    prepared = dict(result)
    work_kind = str(job.payload.get("work_kind", "follow_up_qa"))
    operator_message = str(job.payload.get("operator_message", "")).strip()
    if work_kind == "follow_up_qa" and job.persona == "consultant":
        coerce_consultant_advisory_result(prepared, goal=operator_message)
    return prepared


def extract_follow_up_answer(result: dict[str, Any]) -> str:
    if isinstance(result.get("personas"), list) or isinstance(result.get("sub_goals"), dict):
        return json.dumps(result, indent=2, ensure_ascii=False)[:8000]
    answer = result.get("answer")
    if isinstance(answer, str) and answer.strip() and not _is_structured_finding(result):
        return answer.strip()
    if _is_structured_finding(result):
        return json.dumps(result, indent=2, ensure_ascii=False)[:8000]
    for key in ("summary", "text", "response", "raw_response", "raw"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(result, ensure_ascii=False)[:8000]


class FollowUpAnswerPublisher:
    def __init__(
        self,
        *,
        memory_writer: MemoryWriteService | None = None,
        engagement_egress: EngagementEgressPort | None = None,
        engagement_store: EngagementStateStore | None = None,
        record_memory_write=None,
        enqueue_follow_up=None,
        record_follow_up_completed=None,
        record_follow_up_failed=None,
    ) -> None:
        self._memory_writer = memory_writer
        self._engagement_egress = engagement_egress
        self._engagement_store = engagement_store
        self._record_memory_write = record_memory_write or (lambda _t, _m: None)
        self._enqueue_follow_up = enqueue_follow_up
        self._record_follow_up_completed = record_follow_up_completed or (lambda _k: None)
        self._record_follow_up_failed = record_follow_up_failed or (lambda _k: None)

    def publish_success(self, *, job: WorkerJob, result: dict[str, Any], investigation_id: str) -> str:
        follow_up_id = str(job.payload.get("follow_up_id", ""))
        prepared = prepare_follow_up_result(job, result)
        text = extract_follow_up_answer(prepared)
        content_type = _content_type_for(prepared)
        work_kind = str(job.payload.get("work_kind", "follow_up_qa"))
        finding_body = prepared if content_type in ("finding", "plan") else None

        if self._memory_writer is not None and follow_up_id:
            self._memory_writer.append_conversation_turn(
                tenant_id=job.tenant_id,
                investigation_id=investigation_id,
                role="assistant",
                text=text,
                follow_up_id=follow_up_id,
                job_id=job.job_id,
                persona=job.persona,
                source_agent=job.persona,
                work_kind=work_kind,
                content_type=content_type,
                finding=finding_body,
                status="completed",
            )
            self._record_memory_write(job.tenant_id, "conversation")
        if self._engagement_egress is not None and follow_up_id:
            publish_assistant_snapshot(
                egress=self._engagement_egress,
                engagement_id=investigation_id,
                job_id=job.job_id,
                persona=job.persona,
                tenant_id=job.tenant_id,
                text=text,
            )
            event_type = (
                "follow_up_plan_complete"
                if work_kind == "follow_up_plan"
                else "follow_up_complete"
            )
            self._engagement_egress.publish_event(
                investigation_id,
                event_type,
                {
                    "tenant_id": job.tenant_id,
                    "follow_up_id": follow_up_id,
                    "job_id": job.job_id,
                    "persona": job.persona,
                    "text": text,
                    "work_kind": work_kind,
                    "content_type": content_type,
                    "finding": finding_body,
                },
            )
        self._drain_pending_follow_ups(job, investigation_id)
        self._record_follow_up_completed(work_kind)
        return text

    def publish_failure(self, *, job: WorkerJob, investigation_id: str, error: str) -> None:
        follow_up_id = str(job.payload.get("follow_up_id", ""))
        work_kind = str(job.payload.get("work_kind", "follow_up_qa"))
        self._record_follow_up_failed(work_kind)
        if self._memory_writer is not None and follow_up_id:
            self._memory_writer.append_conversation_turn(
                tenant_id=job.tenant_id,
                investigation_id=investigation_id,
                role="assistant",
                text=error[:500],
                follow_up_id=follow_up_id,
                job_id=job.job_id,
                persona=job.persona,
                source_agent=job.persona,
                work_kind=work_kind,
                content_type="markdown",
                status="failed",
            )
            self._record_memory_write(job.tenant_id, "conversation")
        if self._engagement_egress is None or not follow_up_id:
            return
        self._engagement_egress.publish_event(
            investigation_id,
            "follow_up_failed",
            {
                "tenant_id": job.tenant_id,
                "follow_up_id": follow_up_id,
                "job_id": job.job_id,
                "persona": job.persona,
                "error": error[:500],
                "work_kind": work_kind,
            },
        )

    def _drain_pending_follow_ups(self, job: WorkerJob, investigation_id: str) -> None:
        if self._engagement_store is None:
            return
        engagement = self._engagement_store.get(job.tenant_id, investigation_id)
        if engagement is None or not engagement.pending_follow_ups:
            return
        pending = list(engagement.pending_follow_ups)
        next_item = pending.pop(0)
        engagement.pending_follow_ups = pending
        self._engagement_store.upsert(engagement)
        if self._enqueue_follow_up is None:
            return
        enqueue_pending = getattr(self._enqueue_follow_up, "enqueue_pending", None)
        if not callable(enqueue_pending):
            return
        enqueue_pending(
            tenant_id=job.tenant_id,
            engagement_id=investigation_id,
            follow_up_id=str(next_item.get("follow_up_id", "")),
            message=str(next_item.get("message", "")),
            work_kind=str(next_item.get("work_kind", "follow_up_qa")),
        )
