from __future__ import annotations

from typing import Any

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
    workspace_id: str = "",
    organization_id: str = "",
    sub: str = "",
    authz_decision: str = "",
    sandbox_id: str = "",
    memory_entries_loaded: int = 0,
    trace_name: str = "",
) -> dict[str, Any]:
    """Vendor-neutral trace tags and metadata for worker/agent runs."""
    cid = correlation_id or get_correlation_id() or event_id or job_id
    inv_id = investigation_id or cid
    trace_session = inv_id or cid or session_id or job_id
    tags = [f"persona:{persona}"]
    if cid:
        tags.append(f"correlation:{cid}")
    if inv_id:
        tags.append(f"investigation:{inv_id}")
        tags.append(f"engagement:{inv_id}")
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
        "workspace_id": workspace_id,
        "organization_id": organization_id,
        "sub": sub,
        "authz_decision": authz_decision,
        "sandbox_id": sandbox_id,
        "memory_entries_loaded": memory_entries_loaded,
        "trace_session_id": trace_session,
        "trace_user_id": tenant_id,
        "trace_name": name,
        "trace_tags": tags,
    }
    return {
        "tags": tags,
        "metadata": {k: v for k, v in metadata.items() if v or k in ("tenant_id", "trace_tags")},
    }


def build_sgr_trace_metadata(
    *,
    phase: str,
    task_completed: bool = False,
    enough_data: bool = False,
) -> dict[str, str]:
    return {
        "sgr.phase": phase,
        "sgr.task_completed": str(task_completed).lower(),
        "sgr.enough_data": str(enough_data).lower(),
    }


def to_langfuse_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Map neutral keys to Langfuse CallbackHandler v4 metadata keys."""
    out = dict(metadata)
    if "trace_session_id" in out:
        out["langfuse_session_id"] = out.pop("trace_session_id")
    if "trace_user_id" in out:
        out["langfuse_user_id"] = out.pop("trace_user_id")
    if "trace_name" in out:
        out["langfuse_trace_name"] = out.pop("trace_name")
    if "trace_tags" in out:
        out["langfuse_tags"] = out.pop("trace_tags")
    return out


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
    lf_meta = to_langfuse_metadata(trace["metadata"])
    merged["metadata"] = {**base.get("metadata", {}), **lf_meta}
    merged["tags"] = [*base.get("tags", []), *trace["tags"]]
    return merged
