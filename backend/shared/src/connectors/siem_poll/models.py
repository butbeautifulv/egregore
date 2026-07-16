from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from cys_core.domain.events.models import SecurityEvent, Severity

_SEVERITY_MAP: dict[str, Severity] = {
    "info": "info",
    "informational": "info",
    "low": "low",
    "medium": "medium",
    "moderate": "medium",
    "high": "high",
    "critical": "critical",
    "severe": "critical",
    "1": "info",
    "2": "low",
    "3": "low",
    "4": "medium",
    "5": "medium",
    "6": "high",
    "7": "high",
    "8": "critical",
    "9": "critical",
    "10": "critical",
}


class SiemRawAlert(BaseModel):
    """Normalized intermediate form of a SIEM search/notable result."""

    id: str = ""
    rule_name: str = ""
    severity: str = "medium"
    message: str = ""
    host: str = ""
    source_type: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_siem_record(cls, record: dict[str, Any]) -> SiemRawAlert:
        alert_id = str(record.get("id") or record.get("_id") or record.get("event_id") or "")
        if not alert_id:
            alert_id = f"siem-{uuid.uuid4().hex[:12]}"
        return cls(
            id=alert_id,
            rule_name=str(record.get("rule_name") or record.get("rule") or record.get("search_name") or ""),
            severity=str(record.get("severity") or record.get("urgency") or "medium"),
            message=str(record.get("message") or record.get("description") or record.get("_raw") or ""),
            host=str(record.get("host") or record.get("dest") or record.get("src_host") or ""),
            source_type=str(record.get("source_type") or record.get("sourcetype") or ""),
            raw=record,
        )


def map_siem_severity(raw: str) -> Severity:
    key = raw.strip().lower()
    return _SEVERITY_MAP.get(key, "medium")


def normalize_siem_alert(alert: SiemRawAlert, *, source: str = "siem_poll") -> SecurityEvent:
    """Map a SIEM alert to the platform SecurityEvent schema."""
    payload: dict[str, Any] = {
        "rule_name": alert.rule_name,
        "message": alert.message,
        "host": alert.host,
        "source_type": alert.source_type,
        "siem_raw": alert.raw,
    }
    return SecurityEvent(
        id=alert.id,
        type="siem.alert",
        source=source,
        severity=map_siem_severity(alert.severity),
        payload=payload,
        correlation_id=alert.id,
    )
