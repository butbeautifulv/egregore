from __future__ import annotations

from typing import Any

from bootstrap.settings import settings
from cys_core.observability.tracing import get_correlation_id


def _trace_name(*, persona: str, job_id: str, explicit: str) -> str:
    if explicit:
        return explicit
    if job_id:
        return f"egregore-worker-{persona}"
    return f"egregore-agent-{persona}"


def build_job_trace_metadata(
    *,
    persona: str,
    job_id: str = "",
    event_id: str = "",
    correlation_id: str = "",
    investigation_id: str = "",
    session_id: str = "",
    tenant_id: str = "default",
    sandbox_id: str = "",
    memory_entries_loaded: int = 0,
    trace_name: str = "",
) -> dict[str, Any]:
    """Langfuse/LangChain trace tags and metadata for a worker job or agent run."""
    cid = correlation_id or get_correlation_id() or event_id or job_id
    inv_id = investigation_id or cid
    langfuse_session = session_id or inv_id or cid or job_id
    tags = [f"persona:{persona}"]
    if cid:
        tags.append(f"correlation:{cid}")
    if inv_id:
        tags.append(f"investigation:{inv_id}")
    if job_id:
        tags.append(f"job:{job_id}")

    name = _trace_name(persona=persona, job_id=job_id, explicit=trace_name)
    metadata = {
        "persona": persona,
        "job_id": job_id,
        "event_id": event_id,
        "correlation_id": cid,
        "investigation_id": inv_id,
        "tenant_id": tenant_id,
        "sandbox_id": sandbox_id,
        "memory_entries_loaded": memory_entries_loaded,
        # Langfuse LangChain CallbackHandler v4 reads these keys from metadata
        "langfuse_session_id": langfuse_session,
        "langfuse_user_id": tenant_id,
        "langfuse_trace_name": name,
        "langfuse_tags": tags,
    }
    return {
        "tags": tags,
        "metadata": {k: v for k, v in metadata.items() if v or k in ("tenant_id", "langfuse_tags")},
    }


def merge_langchain_config(
    base: dict[str, Any],
    *,
    persona: str,
    job_id: str = "",
    event_id: str = "",
    correlation_id: str = "",
    investigation_id: str = "",
    session_id: str = "",
    tenant_id: str = "default",
    sandbox_id: str = "",
    memory_entries_loaded: int = 0,
    trace_name: str = "",
) -> dict[str, Any]:
    trace = build_job_trace_metadata(
        persona=persona,
        job_id=job_id,
        event_id=event_id,
        correlation_id=correlation_id,
        investigation_id=investigation_id,
        session_id=session_id,
        tenant_id=tenant_id,
        sandbox_id=sandbox_id,
        memory_entries_loaded=memory_entries_loaded,
        trace_name=trace_name,
    )
    merged = dict(base)
    merged["metadata"] = {**base.get("metadata", {}), **trace["metadata"]}
    merged["tags"] = [*base.get("tags", []), *trace["tags"]]
    return merged
