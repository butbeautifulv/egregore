from __future__ import annotations

import pytest

from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore


@pytest.mark.unit
def test_job_store_persists_correlation_and_lists_by_investigation():
    store = InMemoryJobStore()
    store.upsert_running(
        "job-1",
        "worker:soc:job-1",
        "soc",
        correlation_id="inv-abc",
        tenant_id="default",
        event_id="evt-1",
    )
    store.upsert_running(
        "job-2",
        "worker:network:job-2",
        "network",
        correlation_id="inv-abc",
        tenant_id="default",
        event_id="evt-1",
    )
    jobs = store.list_by_investigation("default", "inv-abc")
    assert len(jobs) == 2
    assert {job.persona for job in jobs} == {"soc", "network"}
    assert all(job.correlation_id == "inv-abc" for job in jobs)
