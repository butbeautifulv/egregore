from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamContext:
    """Operator-only streaming scope for engagement egress events."""

    engagement_id: str
    job_id: str
    persona: str
    tenant_id: str = "default"
