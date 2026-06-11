from __future__ import annotations

import json
from typing import Any

from langgraph.types import Send, interrupt

from config import settings
from cys_core.domain.assessment.services import AssessmentReportBuilder, HitlPolicy
from cys_core.registry.agents import get_agent_registry
from cys_core.registry.schemas import schema_registry
from cys_core.runtime.agent import get_runtime
from cys_core.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.security.guardrails import OutputGuardrails
from cys_core.security.rate_limit import RedisRateLimiter
from cys_core.security.sanitizer import InputSanitizer
from graph.state import AssessmentState

_sanitizer = InputSanitizer()
_guardrails = OutputGuardrails()
_hitl_policy = HitlPolicy(_guardrails)
_report_builder = AssessmentReportBuilder()
_rate_limiter = RedisRateLimiter()
_bus = SecureAgentBus(signing_key=b"cys-agi-bus-key")
_runtime = get_runtime()
_registry = get_agent_registry()

_TRUST_MAP = {
    "untrusted": AgentTrustLevel.UNTRUSTED,
    "internal": AgentTrustLevel.INTERNAL,
    "privileged": AgentTrustLevel.PRIVILEGED,
    "system": AgentTrustLevel.SYSTEM,
}

for _defn in _registry.all():
    _bus.register_agent(
        _defn.name,
        _TRUST_MAP.get(_defn.trust_level, AgentTrustLevel.INTERNAL),
        _defn.bus_recipients,
    )


def ingest_node(state: AssessmentState) -> dict[str, Any]:
    session_id = state.get("session_id", "assessment")
    _rate_limiter.check(f"assessment:{session_id}")
    raw = state.get("raw_input", "")
    sanitized = _sanitizer.sanitize(raw)
    return {
        "sanitized_input": sanitized,
        "scope": state.get("scope", {"authorized": True}),
        "findings": [],
        "errors": [],
        "approved": False,
    }


def dispatch_node(state: AssessmentState) -> list[Send]:
    payload_base = {
        "sanitized_input": state["sanitized_input"],
        "session_id": state.get("session_id", "assessment"),
    }
    return [
        Send("run_agent", {**payload_base, "agent_name": defn.name})
        for defn in _registry.by_role("specialist")
    ]


async def run_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    agent_name = state["agent_name"]
    session_id = f"{state.get('session_id', 'assessment')}:{agent_name}"
    try:
        result = await _runtime.arun(agent_name, state["sanitized_input"], session_id=session_id)
        message = _bus.send_message(agent_name, "critic", "finding", {"agent": agent_name, "data": result})
        _bus.receive_message("critic", message)
        return {"findings": [{"agent": agent_name, "data": result}]}
    except Exception as exc:
        _bus.record_agent_failure(agent_name)
        return {
            "errors": [f"{agent_name}: {exc}"],
            "findings": [{"agent": agent_name, "data": {}, "error": str(exc)}],
        }


async def critic_node(state: AssessmentState) -> dict[str, Any]:
    session_id = state.get("session_id", "assessment")
    findings_blob = json.dumps(state.get("findings", []), ensure_ascii=False)
    critic_schema = schema_registry.get("CriticResult")
    try:
        result = await _runtime.arun("critic", findings_blob, session_id=f"{session_id}:critic")
        if critic_schema:
            validated = _guardrails.validate_schema(result, critic_schema)
            return {"critic_result": validated.model_dump()}
        return {"critic_result": result}
    except Exception as exc:
        return {"critic_result": {"trust_score": 0.0, "issues_detected": [str(exc)]}, "errors": [f"critic: {exc}"]}


def hitl_gate_node(state: AssessmentState) -> dict[str, Any]:
    critic = state.get("critic_result") or {}
    findings = state.get("findings", [])
    decision = _hitl_policy.decide(
        critic_result=critic,
        findings=findings,
        trust_score_threshold=settings.trust_score_threshold,
        stage=settings.stage,
        auto_approve_threshold=settings.hitl_auto_approve_threshold,
    )

    if decision.interrupt_preview is None:
        return {"approved": decision.approved, "pending_approval": decision.pending_approval}

    manual_decision = interrupt(decision.interrupt_preview)
    resolved = _hitl_policy.decide(
        critic_result=critic,
        findings=findings,
        trust_score_threshold=settings.trust_score_threshold,
        stage=settings.stage,
        auto_approve_threshold=settings.hitl_auto_approve_threshold,
        manual_decision=manual_decision,
    )
    return {"approved": resolved.approved, "pending_approval": resolved.pending_approval}


def report_node(state: AssessmentState) -> dict[str, Any]:
    return {"report": _report_builder.build(state)}
