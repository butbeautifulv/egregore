from __future__ import annotations

RAW_EVENTS_TOPIC = "security.events.raw"
BUS_FINDINGS_TOPIC = "bus.findings"
DLQ_TOPIC = "worker.jobs.dlq"
AUDIT_TOOL_INVOCATIONS_TOPIC = "audit.tool.invocations"
PAUSED_JOBS_TOPIC = "worker.jobs.paused"
AUDIT_HITL_APPROVALS_TOPIC = "audit.hitl.approvals"
AUDIT_SKILL_LOADS_TOPIC = "audit.skill.loads"
RAG_INGEST_STAGING_TOPIC = "interfaces.rag.ingest.staging"
AWAITING_APPROVAL_TOPIC = "security.events.awaiting_approval"
ESCALATION_EVENTS_TOPIC = "security.events.escalation"

WORKER_JOBS_TOPIC = "worker.jobs"


def worker_job_topic(_persona: str) -> str:
    """Deprecated: per-persona topics replaced by WORKER_JOBS_TOPIC."""
    return WORKER_JOBS_TOPIC
