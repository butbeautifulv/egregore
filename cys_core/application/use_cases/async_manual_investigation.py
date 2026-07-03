from __future__ import annotations

import logging
from typing import Any, Protocol

from cys_core.application.use_cases.dispatch_event import JobEnqueuer
from cys_core.application.use_cases.plan_investigation import PlanInvestigation
from cys_core.domain.events.models import SecurityEvent
from cys_core.observability.langfuse_client import flush_langfuse

logger = logging.getLogger(__name__)


class InvestigationStatusNotifier(Protocol):
    def record_investigation_update(self, payload: dict[str, Any]) -> None: ...


async def complete_manual_investigation_planning(
    event: SecurityEvent,
    payload: dict[str, Any],
    *,
    plan_investigation: PlanInvestigation,
    enqueuer: JobEnqueuer,
    status_notifier: InvestigationStatusNotifier | None = None,
) -> list[str]:
    """Run LLM planner and enqueue worker jobs (background task after HTTP 202)."""
    try:
        plan = await plan_investigation.execute(event)
        enriched = {**payload, **plan_investigation.to_worker_jobs_payload(plan)}
        job_ids = await enqueuer.enqueue_from_routing(
            event.id,
            plan.personas,
            playbook_id="manual-investigation",
            payload=enriched,
            correlation_id=event.correlation_id or event.id,
            tenant_id=event.tenant_id,
            sequential=bool(plan.depends_on),
        )
        if status_notifier is not None:
            state = plan_investigation.investigation_store.get(
                event.tenant_id, event.correlation_id or event.id
            )
            status_notifier.record_investigation_update(
                {
                    "investigation_id": event.correlation_id or event.id,
                    "tenant_id": event.tenant_id,
                    "planner_status": state.planner_status if state else "ok",
                    "planner_rationale": plan.rationale,
                    "job_ids": job_ids,
                    "personas": plan.personas,
                }
            )
        return job_ids
    except Exception:
        logger.exception("Background manual.investigation planning failed for %s", event.id)
        raise
    finally:
        flush_langfuse()
