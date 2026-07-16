from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.runs.models import InteractionMode, RunContext


class RunCreateIn(BaseModel):
    goal: str
    mode: InteractionMode = InteractionMode.AGENT
    profile_id: str = DEFAULT_PROFILE_ID
    persona: str = "conductor"
    message: str = ""
    tenant_id: str = "default"
    file_paths: list[str] = Field(default_factory=list)


class RunStepIn(BaseModel):
    message: str
    mode: InteractionMode | None = None


class RunOut(BaseModel):
    run_context: dict[str, Any]
    result: dict[str, Any] = Field(default_factory=dict)


class SessionCreateIn(BaseModel):
    goal: str
    mode: InteractionMode = InteractionMode.PLAN
    profile_id: str = DEFAULT_PROFILE_ID
    message: str = ""
    tenant_id: str = "default"


def new_job_context(body: RunCreateIn) -> RunContext:
    job_id = f"run-{uuid4().hex[:12]}"
    return RunContext.one_shot_job(
        job_id,
        tenant_id=body.tenant_id,
        mode=body.mode,
        profile_id=body.profile_id,
    )


def new_session_context(body: SessionCreateIn) -> RunContext:
    session_id = f"session-{uuid4().hex[:12]}"
    return RunContext.from_session_id(
        session_id,
        tenant_id=body.tenant_id,
        mode=body.mode,
        profile_id=body.profile_id,
    )
