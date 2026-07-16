from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interfaces.worker.daemon import WorkerDaemon


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_daemon_processes_jobs_then_idles_out():
    results = [
        SimpleNamespace(model_dump=lambda: {"success": True}),
        None,
        None,
    ]

    orch = MagicMock()
    orch.process_next = AsyncMock(side_effect=results)
    container = MagicMock()
    container.get_worker_orchestrator.return_value = orch
    container.get_trace_backend.return_value = MagicMock(flush=MagicMock())

    queue = MagicMock()
    queue.name = "test-queue"
    del queue.aclose
    container.get_job_queue.return_value = queue
    container.get_engagement_egress.return_value = MagicMock(active_backend="memory")

    with (
        patch("interfaces.worker.daemon.get_container", return_value=container),
        patch("interfaces.worker.daemon.flush_langfuse") as flush_mock,
        patch("bootstrap.bus_lifecycle.wire_async_bus", new_callable=AsyncMock),
    ):
        daemon = WorkerDaemon("soc", max_jobs=1, idle_timeout=0.1)
        processed = await daemon.run()
    assert processed == 1
    assert flush_mock.call_count == 2
    container.get_worker_orchestrator.assert_called_once_with(persona="soc")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_daemon_request_stop():
    daemon = WorkerDaemon("soc", idle_timeout=60.0)
    daemon.request_stop()
    assert daemon._stop is True
