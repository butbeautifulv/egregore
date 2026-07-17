from __future__ import annotations

import pytest

from cys_core.observability.metrics import metrics, seed_agent_trust_gauges


@pytest.mark.unit
def test_metrics_counters_increment():
    metrics.record_event_ingested("siem_alert")
    metrics.record_tool_invocation("rag_query", success=True)
    metrics.record_sanitizer_block("tool", "hard")
    metrics.record_rag_retrieval("acme", denied=True)
    metrics.record_approval_bypass("invalid_approval_id")
    metrics.refresh_hitl_pending(2)
    metrics.set_agent_trust_score("soc", 0.75)


@pytest.mark.unit
def test_track_worker_job_observes_histogram():
    with metrics.track_worker_job("soc") as state:
        state["status"] = "success"


@pytest.mark.unit
def test_seed_agent_trust_gauges_runs():
    seed_agent_trust_gauges()
