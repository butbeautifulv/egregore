from __future__ import annotations

from pydantic import BaseModel, field_validator

from cys_core.domain.runs.models import RunContext

MAX_PERSONA_OVERLAY_LEN = 2000
MAX_SPAWN_DEPTH = 5


class SpawnWorkerPayload(BaseModel):
    parent_context: RunContext
    persona: str
    sub_goal: str
    idempotency_key: str = ""
    persona_overlay: str = ""

    @field_validator("persona_overlay")
    @classmethod
    def _cap_overlay(cls, value: str) -> str:
        return value[:MAX_PERSONA_OVERLAY_LEN]


def sanitize_persona_overlay(text: str) -> str:
    """Strip control chars and cap length for dynamic persona instructions."""
    cleaned = "".join(ch for ch in text if ch == "\n" or ch >= " ")
    return cleaned[:MAX_PERSONA_OVERLAY_LEN]
