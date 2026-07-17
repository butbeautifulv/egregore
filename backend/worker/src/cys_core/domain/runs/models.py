from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from cys_core.domain.events.models import SecurityEvent
    from cys_core.domain.workers.models import WorkerJob


class ContextKind(str, Enum):
    JOB = "job"
    EVENT = "event"
    INVESTIGATION = "investigation"
    SESSION = "session"
    BATCH = "batch"
    STREAM = "stream"


class InteractionMode(str, Enum):
    PLAN = "plan"
    ASK = "ask"
    AGENT = "agent"
    DEBUG = "debug"


def build_correlation_key(kind: ContextKind, context_id: str) -> str:
    return f"{kind.value}:{context_id}"


class RunContext(BaseModel):
    """Universal correlation scope for runs, events, and optional sessions."""

    context_id: str
    kind: ContextKind
    tenant_id: str = "default"
    parent_context_id: str | None = None
    parent_kind: ContextKind | None = None
    mode: InteractionMode | None = None
    profile_id: str = "cybersec-soc"
    spawn_depth: int = 0
    correlation_key: str = ""

    @model_validator(mode="after")
    def _fill_correlation_key(self) -> RunContext:
        if not self.correlation_key:
            object.__setattr__(self, "correlation_key", build_correlation_key(self.kind, self.context_id))
        return self

    @classmethod
    def from_event(cls, event: SecurityEvent) -> RunContext:
        context_id = event.correlation_id or event.id
        return cls(
            context_id=context_id,
            kind=ContextKind.EVENT,
            tenant_id=event.tenant_id,
        )

    @classmethod
    def from_job(cls, job: WorkerJob) -> RunContext:
        context_id = job.job_id
        parent_id = job.correlation_id or None
        return cls(
            context_id=context_id,
            kind=ContextKind.JOB,
            tenant_id=job.tenant_id,
            parent_context_id=parent_id if parent_id and parent_id != job.job_id else None,
            parent_kind=ContextKind.EVENT if parent_id else None,
            spawn_depth=int(job.payload.get("spawn_depth", 0)),
        )

    @classmethod
    def from_session_id(
        cls,
        session_id: str,
        *,
        tenant_id: str = "default",
        mode: InteractionMode | None = None,
        profile_id: str = "cybersec-soc",
    ) -> RunContext:
        return cls(
            context_id=session_id,
            kind=ContextKind.SESSION,
            tenant_id=tenant_id,
            mode=mode,
            profile_id=profile_id,
        )

    @classmethod
    def one_shot_job(
        cls,
        job_id: str,
        *,
        tenant_id: str = "default",
        mode: InteractionMode | None = InteractionMode.AGENT,
        profile_id: str = "cybersec-soc",
    ) -> RunContext:
        return cls(
            context_id=job_id,
            kind=ContextKind.JOB,
            tenant_id=tenant_id,
            mode=mode,
            profile_id=profile_id,
        )

    def spawn_child(self, child_id: str, *, persona: str = "") -> RunContext:
        """Create child job context for subagent spawn."""
        _ = persona
        return RunContext(
            context_id=child_id,
            kind=ContextKind.JOB,
            tenant_id=self.tenant_id,
            parent_context_id=self.context_id,
            parent_kind=self.kind,
            mode=self.mode,
            profile_id=self.profile_id,
            spawn_depth=self.spawn_depth + 1,
        )

    def is_stateful(self) -> bool:
        return self.kind in (ContextKind.SESSION, ContextKind.INVESTIGATION)
