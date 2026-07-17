from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class EvalQualitySignal(BaseModel):
    """Normalized quality signals derived from eval runs."""

    source_suite: str
    metric: str
    value: float
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

