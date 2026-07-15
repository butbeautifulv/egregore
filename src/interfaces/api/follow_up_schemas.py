from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from cys_core.domain.follow_up.models import FollowUpMode


class FollowUpIn(BaseModel):
    message: str
    tenant_id: str = "default"
    mode: FollowUpMode = "auto"
    enqueue: bool = True


class FollowUpOut(BaseModel):
    follow_up_id: str
    status: Literal["queued", "pending", "persisted"]
    work_kind: str
    job_id: str | None = None


class FollowUpTurnOut(BaseModel):
    id: str
    role: str
    text: str
    created_at: str
    follow_up_id: str
    job_id: str | None = None
    persona: str | None = None
    status: str = "completed"
    work_kind: str | None = None
    mode: FollowUpMode | None = None
    content_type: Literal["finding", "plan", "markdown"] | None = None
    finding: dict[str, Any] | None = None


class FollowUpListOut(BaseModel):
    turns: list[FollowUpTurnOut] = Field(default_factory=list)


class FollowUpPendingOut(BaseModel):
    pending: list[dict[str, Any]] = Field(default_factory=list)
