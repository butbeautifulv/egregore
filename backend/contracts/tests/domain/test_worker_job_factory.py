from __future__ import annotations

import pytest

from cys_core.domain.workers.job_factory import jobs_for_routing


@pytest.mark.unit
def test_jobs_for_routing_parallel_has_no_dependencies():
    jobs = jobs_for_routing("evt-1", ["soc", "network"], sequential=False)
    assert len(jobs) == 2
    assert all(job.depends_on_persona == "" for job in jobs)
    assert jobs[0].persona == "soc"
    assert jobs[1].persona == "network"
    assert jobs[0].correlation_id == "evt-1"


@pytest.mark.unit
def test_jobs_for_routing_sequential_sets_dependencies():
    jobs = jobs_for_routing(
        "evt-1",
        ["soc", "network", "compliance"],
        sequential=True,
        correlation_id="inv-1",
    )
    assert jobs[0].depends_on_persona == ""
    assert jobs[1].depends_on_persona == "soc"
    assert jobs[2].depends_on_persona == "network"
    assert jobs[0].correlation_id == "inv-1"
    assert jobs[0].event_id == "evt-1"
