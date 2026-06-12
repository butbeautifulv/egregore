from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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

    with patch("interfaces.worker.daemon.WorkerOrchestrator") as orch_cls:
        orch = orch_cls.return_value
        orch.process_next = AsyncMock(side_effect=results)
        daemon = WorkerDaemon("soc", max_jobs=1, idle_timeout=0.1)
        with patch("asyncio.get_running_loop") as loop_mock:
            loop_mock.return_value.add_signal_handler = lambda *a, **k: None
            processed = await daemon.run()
    assert processed == 1
    orch_cls.assert_called_once_with(persona="soc")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_daemon_request_stop():
    daemon = WorkerDaemon("soc", idle_timeout=60.0)
    daemon.request_stop()
    assert daemon._stop is True
