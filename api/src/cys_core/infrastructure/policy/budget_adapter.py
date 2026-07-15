from __future__ import annotations

from cys_core.domain.policy.pure import persona_budget_pure
from cys_core.domain.workers.models import PersonaBudget, WorkerJob


def persona_budget_for(persona: str) -> PersonaBudget:
    from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog

    try:
        entry = get_agent_catalog().get_agent(persona)
    except Exception:
        entry = None
    return persona_budget_pure(persona, entry)


def enrich_job_budget(job: WorkerJob) -> WorkerJob:
    return job.apply_budget(persona_budget_for(job.persona))
