from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PersonaQualityEventKind(str, Enum):
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    CRITIC_PASS = "critic_pass"
    CRITIC_FAIL = "critic_fail"
    TRACE_CRITIC_PASS = "trace_critic_pass"
    TRACE_CRITIC_FAIL = "trace_critic_fail"
    HITL_PAUSE = "hitl_pause"
    BUS_FAILURE = "bus_failure"


class PersonaQualityEvent(BaseModel):
    persona: str
    profile_id: str = "cybersec-soc"
    kind: PersonaQualityEventKind
    trust_signal: float = 0.5
    cost_usd: float = 0.0
    metadata: dict = Field(default_factory=dict)
