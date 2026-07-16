from __future__ import annotations

import pytest

from cys_core.domain.workers.bus_job_ids import is_bus_worker_job_id


@pytest.mark.unit
def test_is_bus_worker_job_id_matches_revision_jobs() -> None:
    assert is_bus_worker_job_id("soc-bus-78a3e45a")
    assert is_bus_worker_job_id("intel-bus-548b2bf9")
    assert is_bus_worker_job_id("network-bus-88bd6279")


@pytest.mark.unit
def test_is_bus_worker_job_id_rejects_engagement_job_ids() -> None:
    assert not is_bus_worker_job_id("soc-eng-bus-reconcile-abc")
    assert not is_bus_worker_job_id("soc-inv-bus-gate-aaa")
