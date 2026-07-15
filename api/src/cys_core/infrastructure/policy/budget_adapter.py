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


def resolve_job_cost_context(budgeted: WorkerJob, *, default_cost_rate: float) -> tuple[str, float]:
    """Resolve (profile_id, cost_rate) for a budgeted job.

    Used both by the Dispatcher (WorkerOrchestrator.run_job, to configure
    JobBudgetTracker before handing off to an ExecutionBackend) and by
    out-of-process backends whose child must reconfigure the same tracker
    itself, since it doesn't cross the process boundary (see Discovery D in
    docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md). Deterministic given
    budgeted.persona/payload plus shared catalog/policy state, so parent and
    child resolve the same values independently without needing to ship them
    over the wire.

    ``default_cost_rate`` (the settings-level fallback used when the catalog
    policy doesn't define a per-profile rate) is a caller-supplied parameter
    rather than read from ``bootstrap.settings`` here — cys_core/infrastructure
    must not import bootstrap directly (hexagon inversion, enforced by
    scripts/verify_import_boundaries.py); only the interfaces-layer callers
    (WorkerOrchestrator, cmd_run_sandboxed_job) have a Settings instance.
    """
    from cys_core.domain.catalog.profile_id import resolve_profile_id
    from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog
    from cys_core.infrastructure.catalog.profile_policy import get_cost_per_1k_tokens

    catalog_entry = get_agent_catalog().get_agent(budgeted.persona)
    profile_id = resolve_profile_id(payload=budgeted.payload, catalog_entry=catalog_entry)
    cost_rate = get_cost_per_1k_tokens(profile_id)
    if cost_rate <= 0:
        cost_rate = default_cost_rate
    return profile_id, cost_rate
