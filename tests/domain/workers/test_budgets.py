from __future__ import annotations

import pytest

from cys_core.domain.workers.budgets import enrich_job_budget, persona_budget
from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
def test_persona_budget_defaults():
    soc = persona_budget("soc")
    assert soc.max_cost_usd == 2.0
    redteam = persona_budget("redteam")
    assert redteam.max_cost_usd == 5.0


@pytest.mark.unit
def test_enrich_job_budget_applies_persona_defaults():
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc")
    budget = persona_budget("soc")
    enriched = enrich_job_budget(job, budget)
    assert enriched.max_tokens == 50_000
    assert enriched.max_cost_usd == 2.0
    assert enriched.max_tool_calls == 50


@pytest.mark.unit
def test_enrich_job_budget_respects_explicit_limits():
    job = WorkerJob(
        job_id="j1",
        event_id="e1",
        persona="soc",
        max_tokens=10_000,
        max_cost_usd=0.5,
        max_tool_calls=5,
    )
    enriched = enrich_job_budget(job, persona_budget("soc"))
    assert enriched.max_tokens == 10_000
    assert enriched.max_cost_usd == 0.5
    assert enriched.max_tool_calls == 5
