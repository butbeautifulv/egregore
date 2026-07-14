from __future__ import annotations

from typing import Any

from cys_core.application.bus_engagement import normalize_correlation_id


class ControlMessageHandler:
    """Shared envelope parsing for coordinator/critic control-plane handlers."""

    @staticmethod
    def extract_payload(envelope: dict[str, Any]) -> dict[str, Any]:
        payload = envelope.get("payload", {})
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def extract_context(cls, envelope: dict[str, Any]) -> dict[str, Any]:
        payload = cls.extract_payload(envelope)
        event_id = str(payload.get("event_id", "n/a"))
        tenant_id = str(payload.get("tenant_id", "default"))
        investigation_id = normalize_correlation_id(
            str(payload.get("correlation_id", payload.get("event_id", event_id))),
            payload,
        )
        finding = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        sender = str(envelope.get("sender", "unknown"))
        # NOTE(evidence-grounding-consolidation, 2026-07-14): this `job_id` is synthesized, not
        # the real WorkerJob.job_id — `finding_publisher.publish()` already puts the real job_id
        # in `payload["job_id"]` but it is not read here. Flagged while investigating whether
        # process_finding_critic could be threaded a job_id to unify its manifest lookup with
        # run_worker_job's; see the note above `record_evidence_manifest` in
        # cys_core/application/workers/tool_execution_tracker.py for why that consolidation was
        # not made (a correct job_id here would be necessary but not sufficient — the underlying
        # manifest store is process-local either way). Left as-is; not in scope to change.
        job_id = f"{sender}:{investigation_id}" if investigation_id else f"{sender}:unknown"
        return {
            "sender": sender,
            "event_id": event_id,
            "tenant_id": tenant_id,
            "investigation_id": investigation_id,
            "engagement_id": investigation_id,
            "finding": finding,
            "job_id": job_id,
            "payload": payload,
        }
