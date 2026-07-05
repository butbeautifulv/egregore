from __future__ import annotations

from cys_core.domain.catalog.models import AgentCatalogEntry
from cys_core.domain.policy.defaults import PERSONA_BUDGETS
from cys_core.domain.policy.pure import persona_budget_pure
from cys_core.domain.workers.models import DEFAULT_BUDGET, PersonaBudget, WorkerJob


def persona_budget(persona: str, entry: AgentCatalogEntry | None = None) -> PersonaBudget:
    return persona_budget_pure(persona, entry)


def enrich_job_budget(job: WorkerJob, budget: PersonaBudget) -> WorkerJob:
    return job.apply_budget(budget)


__all__ = ["PERSONA_BUDGETS", "DEFAULT_BUDGET", "PersonaBudget", "persona_budget", "enrich_job_budget"]
