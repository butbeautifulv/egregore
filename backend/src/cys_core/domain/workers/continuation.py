from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from cys_core.domain.evidence.snapshot import EvidenceSnapshot


class JobContinuationKind(StrEnum):
    REVISION = "revision"
    FOLLOW_UP_CHILD = "follow_up_child"


class JobContinuation(BaseModel):
    work_kind: JobContinuationKind
    snapshot: EvidenceSnapshot | None = None
    parent_job_id: str = ""
    notes: str = ""
