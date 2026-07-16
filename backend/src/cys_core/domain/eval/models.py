from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvalRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvalCase(BaseModel):
    id: str
    input: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class EvalDataset(BaseModel):
    id: str
    name: str = ""
    cases: list[EvalCase] = Field(default_factory=list)


class EvalMetric(BaseModel):
    name: str
    value: float
    passed: bool = False
    comment: str = ""


class EvalArtifact(BaseModel):
    name: str
    uri: str
    mime_type: str = "application/json"
    meta: dict[str, Any] = Field(default_factory=dict)


class EvalSampleResult(BaseModel):
    case_id: str
    metrics: list[EvalMetric] = Field(default_factory=list)
    artifacts: list[EvalArtifact] = Field(default_factory=list)


class EvalRun(BaseModel):
    run_id: str
    dataset_id: str
    suite_id: str = ""
    profile_id: str = ""
    persona: str = ""
    model: str = ""
    status: EvalRunStatus = EvalRunStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    results: list[EvalSampleResult] = Field(default_factory=list)

    def start(self) -> None:
        self.status = EvalRunStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def finish_ok(self) -> None:
        self.status = EvalRunStatus.COMPLETED
        self.finished_at = datetime.now(timezone.utc)

