from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.events.models import Severity

TaskKind = Literal["investigation", "consultation", "benchmark", "generic"]


class DomainEvent(BaseModel):
    """Product-neutral ingress event for multi-domain routing."""

    id: str
    domain: str
    event_type: str
    tenant_id: str = "default"
    correlation_id: str = ""
    profile_id: str = DEFAULT_PROFILE_ID
    severity: Severity = "medium"
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = ""


class TaskEvent(DomainEvent):
    """Task-shaped domain event (investigations, consultations, benchmarks)."""

    task_kind: TaskKind = "generic"
