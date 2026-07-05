from __future__ import annotations

from pydantic import BaseModel, Field

from cys_core.domain.runs.trajectory import TraceEvent


class TraceVerdict(BaseModel):
    """Result of action-trace doubter-lite evaluation."""

    score: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict: str = ""
    reasoning: str = ""
    should_rerun: bool = False
    issues: list[str] = Field(default_factory=list)


class ModelCallTraceFields(BaseModel):
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class ToolCallTraceFields(BaseModel):
    tool: str
    args_digest: str = ""
    success: bool = True
    latency_ms: float = 0.0


class MemoryTraceFields(BaseModel):
    operation: str  # memory_read | memory_write
    tenant_id: str = "default"
    investigation_id: str = ""
    entries: int = 0
    memory_type: str = ""
    size: int = 0


class EvalTraceFields(BaseModel):
    suite: str = ""
    metric: str = ""
    score: float = 0.0
    verdict: str = ""


def model_call_trace(name: str, fields: ModelCallTraceFields) -> TraceEvent:
    return TraceEvent(type="model", name=name, payload=fields.model_dump())


def tool_call_trace(name: str, fields: ToolCallTraceFields) -> TraceEvent:
    return TraceEvent(type="tool", name=name, payload=fields.model_dump())


def memory_trace(name: str, fields: MemoryTraceFields) -> TraceEvent:
    return TraceEvent(type="memory", name=name, payload=fields.model_dump())


def eval_trace(name: str, fields: EvalTraceFields) -> TraceEvent:
    return TraceEvent(type="eval", name=name, payload=fields.model_dump())


def policy_trace(name: str, *, rule: str, decision: str, profile_id: str) -> TraceEvent:
    return TraceEvent(
        type="policy",
        name=name,
        payload={"rule": rule, "decision": decision, "profile_id": profile_id},
    )
