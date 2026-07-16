from __future__ import annotations

from cys_core.observability.metrics import metrics


def refresh_platform_gauges(*, tenant_id: str = "default", engagement_store=None, job_store=None) -> None:
    """Update gauges that are derived from stores (HITL queue, active engagements)."""
    if job_store is None:
        from bootstrap.container import get_container

        job_store = get_container().get_job_store()
    try:
        pending = job_store.list_pending_approvals()
        metrics.refresh_hitl_pending(len(pending))
    except Exception:
        pass

    if engagement_store is None:
        from bootstrap.container import get_container

        engagement_store = get_container().get_engagement_state_store()
    try:

        states = engagement_store.list_recent(tenant_id, limit=500)
        active = sum(
            1
            for state in states
            if not state.status.is_terminal()
        )
        metrics.refresh_investigations_active(active)
    except Exception:
        pass
