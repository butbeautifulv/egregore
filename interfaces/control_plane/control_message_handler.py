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
