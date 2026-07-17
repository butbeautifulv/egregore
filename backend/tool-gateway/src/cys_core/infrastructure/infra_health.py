from __future__ import annotations

from typing import Any


def _transport_backend(transport: Any) -> str:
    backend = getattr(transport, "active_backend", None)
    if backend is not None:
        return str(backend)
    if getattr(transport, "_redis", None) is not None:
        return "redis"
    return getattr(transport, "name", "unknown")


def collect_infra_health(
    *,
    queue: Any,
    egress: Any,
    transport: Any,
    job_store: Any,
) -> dict[str, Any]:
    depth_fn = getattr(queue, "queue_depth", None)
    depth = depth_fn() if depth_fn is not None else None
    running_count = 0
    count_fn = getattr(job_store, "count_running", None)
    if count_fn is not None:
        running_count = int(count_fn())

    workers_hint = "ok"
    if isinstance(depth, int) and depth > 0 and running_count == 0:
        workers_hint = "backlog"
    elif isinstance(depth, int) and depth > 0 and running_count > 0:
        workers_hint = "processing"

    return {
        "queue": {
            "backend": getattr(queue, "active_backend", getattr(queue, "name", "unknown")),
            "depth": depth,
        },
        "egress": {
            "backend": getattr(egress, "active_backend", "unknown"),
        },
        "bus_transport": {
            "backend": _transport_backend(transport),
        },
        "workers_hint": workers_hint,
        "running_jobs": running_count,
    }
