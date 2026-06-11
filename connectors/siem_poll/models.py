from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from cys_core.domain.events.models import SecurityEvent, Severity

SIEM_TYPE_MAP: dict[str, str] = {
    "alert": "siem.alert",
    "siem.alert": "siem.alert",
    "edr": "edr.alert",
    "edr.alert": "edr.alert",
    "endpoint.alert": "edr.alert",
    "iam": "iam.event",
    "iam.event": "iam.event",
    "auth.event": "iam.event",
    "netflow": "netflow.beacon",
    "netflow.beacon": "netflow.beacon",
    "network.beacon": "netflow.beacon",
    "dns": "dns.anomaly",
    "dns.anomaly": "dns.anomaly",
    "default": "siem.alert",
}

SEVERITY_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "info",
    "informational": "info",
    "warning": "low",
    "warn": "low",
    "error": "high",
    "unknown": "info",
}


class RawSiemEvent(BaseModel):
    raw_id: str
    event_type: str
    severity: str
    source: str
    host: str
    message: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tenant_id: str = "default"
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("severity", mode="before")
    @classmethod
    def normalise_severity(cls, v: str) -> str:
        return SEVERITY_MAP.get(v.lower(), "info")


def normalize_event_type(raw_type: str) -> str:
    return SIEM_TYPE_MAP.get(raw_type.lower(), SIEM_TYPE_MAP["default"])


def raw_to_security_event(raw: RawSiemEvent) -> SecurityEvent:
    return SecurityEvent(
        id=raw.raw_id,
        type=normalize_event_type(raw.event_type),  # type: ignore[arg-type]
        source=raw.source,
        severity=raw.severity,  # type: ignore[arg-type]
        payload={
            "host": raw.host,
            "message": raw.message,
            "timestamp": raw.timestamp,
            **raw.extra,
        },
        tenant_id=raw.tenant_id,
        correlation_id=raw.correlation_id,
    )
