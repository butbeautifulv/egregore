from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
@pytest.mark.asyncio
async def test_spawn_worker_uses_aenqueue_in_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.registry import tools as tools_module

    job = WorkerJob(
        job_id="intel-spawn-1",
        event_id="ctx-1",
        persona="intel",
        correlation_id="ctx-1",
    )
    queue = MagicMock()
    queue.enqueue = MagicMock(side_effect=RuntimeError("sync enqueue should not run"))
    queue.aenqueue = AsyncMock(return_value=job.job_id)

    job_store = MagicMock()
    container = MagicMock()
    container.get_job_store.return_value = job_store
    container.get_job_queue.return_value = queue

    monkeypatch.setattr("bootstrap.container.get_container", lambda: container)
    monkeypatch.setattr(
        tools_module,
        "_resolve_spawn_worker_job",
        lambda *args, **kwargs: (
            None,
            job,
            queue,
        ),
    )

    result = await tools_module._aspawn_worker(
        "intel",
        "check ioc",
        context_id="ctx-1",
        tenant_id="default",
    )
    assert "enqueued" in result
    queue.aenqueue.assert_awaited_once_with(job)
    queue.enqueue.assert_not_called()


@pytest.mark.unit
def test_spawn_worker_sync_path_uses_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    from cys_core.registry import tools as tools_module

    job = WorkerJob(
        job_id="soc-spawn-1",
        event_id="ctx-2",
        persona="soc",
        correlation_id="ctx-2",
    )
    queue = MagicMock()
    queue.enqueue = MagicMock(return_value=job.job_id)
    queue.aenqueue = AsyncMock()

    monkeypatch.setattr(
        tools_module,
        "_resolve_spawn_worker_job",
        lambda *args, **kwargs: (None, job, queue),
    )

    result = tools_module._spawn_worker("soc", "triage", context_id="ctx-2")
    assert "enqueued" in result
    queue.enqueue.assert_called_once_with(job)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_queue_sync_enqueue_raises_in_running_loop() -> None:
    from cys_core.infrastructure.kafka_queue import KafkaJobQueue
    from cys_core.domain.workers.models import WorkerJob

    queue = KafkaJobQueue.__new__(KafkaJobQueue)
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc")

    with pytest.raises(RuntimeError, match="Sync adapter called"):
        queue.enqueue(job)
