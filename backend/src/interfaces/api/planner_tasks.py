from __future__ import annotations

from typing import Any

import structlog

from cys_core.domain.events.models import SecurityEvent
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id
from interfaces.api.task_supervisor import BackgroundTaskSupervisor

logger = structlog.get_logger(__name__)


def spawn_engagement_planner(
    request,
    *,
    start,
    event: SecurityEvent,
    payload: dict[str, Any],
    task_name: str = "engagement-planner",
) -> None:
    """Run meta-LLM planner in background after HTTP 202."""

    async def _run_planner() -> None:
        correlation_id = event.correlation_id or event.id
        token = bind_correlation_id(correlation_id)
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            event_id=event.id,
        )
        try:
            await start.plan_async_background(event, payload)
        except Exception:
            logger.exception("Async planner failed for event %s", event.id)
        finally:
            structlog.contextvars.unbind_contextvars("correlation_id", "event_id")
            reset_correlation_id(token)

    supervisor: BackgroundTaskSupervisor | None = getattr(request.app.state, "task_supervisor", None)
    if supervisor is None:
        supervisor = BackgroundTaskSupervisor()
        request.app.state.task_supervisor = supervisor
    supervisor.spawn(_run_planner(), name=task_name)
