from __future__ import annotations

from cys_core.observability.metrics import metrics


def refresh_platform_gauges(*, tenant_id: str = "default") -> None:
    """Update gauges that are derived from stores (HITL queue, investigations)."""
    from bootstrap.container import get_container
    from interfaces.control_plane.job_store import get_job_store
    try:
        pending = get_job_store().list_pending_approvals()
        metrics.refresh_hitl_pending(len(pending))
    except Exception:
        pass

    try:
        states = get_container().get_investigation_state_store().list_recent(tenant_id, limit=500)
        active = sum(1 for state in states if state.status in ("open", "in_progress"))
        metrics.refresh_investigations_active(active)
    except Exception:
        pass
