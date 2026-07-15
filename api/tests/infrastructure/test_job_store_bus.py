from __future__ import annotations

from datetime import timedelta

import pytest

from cys_core.domain.workers.models import WorkerJobStatus
from cys_core.infrastructure.job_store.in_memory import InMemoryJobStore


@pytest.mark.unit
def test_list_active_bus_jobs_matches_corrupted_correlation_id() -> None:
    store = InMemoryJobStore()
    wrapped = 'USER_DATA_TO_PROCESS [source=agent_bus]:\n<untrusted_data>\neng-abc123def456\n</untrusted_data>'
    store.upsert_running(
        "soc-bus-deadbeef",
        "worker:soc:soc-bus-deadbeef",
        "soc",
        correlation_id=wrapped,
        tenant_id="default",
    )
    active = store.list_active_bus_jobs("default", "eng-abc123def456")
    assert len(active) == 1
    assert active[0].job_id == "soc-bus-deadbeef"
    assert store.count_active_bus_jobs("default", "eng-abc123def456") == 1


@pytest.mark.unit
def test_list_stale_bus_jobs_only_returns_old_active_jobs() -> None:
    store = InMemoryJobStore()
    store.upsert_running(
        "soc-bus-fresh",
        "worker:soc:soc-bus-fresh",
        "soc",
        correlation_id="eng-stale-test",
    )
    store._updated_at["soc-bus-fresh"] = store._updated_at["soc-bus-fresh"] - timedelta(seconds=600)

    store.upsert_running(
        "intel-bus-fresh",
        "worker:intel:intel-bus-fresh",
        "intel",
        correlation_id="eng-stale-test",
    )

    stale = store.list_stale_bus_jobs("default", "eng-stale-test", older_than_s=300.0)
    assert [item.job_id for item in stale] == ["soc-bus-fresh"]
    assert store.list_active_bus_jobs("default", "eng-stale-test")
    assert len(store.list_active_bus_jobs("default", "eng-stale-test")) == 2


@pytest.mark.unit
def test_upsert_normalizes_correlation_id() -> None:
    store = InMemoryJobStore()
    wrapped = "prefix eng-abc123def456 suffix"
    record = store.upsert_pending(
        "soc-bus-norm",
        "soc",
        correlation_id=wrapped,
    )
    assert record.correlation_id == "eng-abc123def456"
