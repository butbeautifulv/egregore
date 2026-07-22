from __future__ import annotations

from typing import Any, Protocol


class EngagementEgressPort(Protocol):
    def publish_event(self, engagement_id: str, event_type: str, payload: dict[str, Any]) -> None: ...


class JobStoreLookup(Protocol):
    def get(self, job_id: str) -> Any | None: ...


def _engagement_id_for_job(job_store: JobStoreLookup, job_id: str) -> str | None:
    record = job_store.get(job_id)
    if record is None:
        return None
    correlation_id = getattr(record, "correlation_id", None) or ""
    return correlation_id or None


def publish_hitl_pending(
    egress: EngagementEgressPort | None,
    job_store: JobStoreLookup,
    preview: dict[str, Any],
    pending: Any,
) -> None:
    if egress is None:
        return
    job_id = str(preview.get("job_id") or getattr(pending, "job_id", "") or "")
    engagement_id = _engagement_id_for_job(job_store, job_id)
    if not engagement_id:
        return
    egress.publish_event(
        engagement_id,
        "hitl_pending",
        {
            "job_id": job_id,
            "approval_id": preview.get("approval_id") or getattr(pending, "approval_id", ""),
            "persona": preview.get("persona") or getattr(pending, "persona", ""),
            "tool_name": preview.get("tool") or getattr(pending, "tool_name", ""),
            "tool_args": preview.get("args") or getattr(pending, "tool_args", {}),
            "risk_level": preview.get("risk") or getattr(pending, "risk_level", ""),
            "session_id": preview.get("session_id") or getattr(pending, "session_id", ""),
        },
    )


def publish_hitl_resolved(
    egress: EngagementEgressPort | None,
    *,
    correlation_id: str,
    job_id: str,
    approval_id: str,
    decision: str,
    actor: str = "operator",
) -> None:
    if egress is None or not correlation_id:
        return
    egress.publish_event(
        correlation_id,
        "hitl_resolved",
        {
            "job_id": job_id,
            "approval_id": approval_id,
            "decision": decision,
            "actor": actor,
        },
    )
