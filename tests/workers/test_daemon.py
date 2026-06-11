from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.domain.workers.models import RunResult
from workers.daemon import WorkerDaemon


def make_result(job_id: str = "j1", persona: str = "soc", success: bool = True) -> RunResult:
    return RunResult(job_id=job_id, persona=persona, success=success)


@pytest.mark.asyncio
async def test_daemon_stops_after_max_jobs():
    orchestrator = MagicMock()
    orchestrator.process_next = AsyncMock(return_value=make_result())

    daemon = WorkerDaemon(orchestrator=orchestrator, max_jobs=3)
    count = await daemon.run()
    assert count == 3


@pytest.mark.asyncio
async def test_daemon_stops_on_idle_timeout():
    orchestrator = MagicMock()
    orchestrator.process_next = AsyncMock(return_value=None)

    daemon = WorkerDaemon(orchestrator=orchestrator, idle_timeout=0.3)
    count = await daemon.run()
    assert count == 0


@pytest.mark.asyncio
async def test_daemon_skips_wrong_persona():
    results = [
        make_result(job_id="j1", persona="network"),  # wrong persona
        make_result(job_id="j2", persona="soc"),        # correct
        None,
    ]
    orchestrator = MagicMock()
    orchestrator.process_next = AsyncMock(side_effect=results)

    daemon = WorkerDaemon(orchestrator=orchestrator, persona="soc", max_jobs=1, idle_timeout=1.0)
    count = await daemon.run()
    assert count == 1


@pytest.mark.asyncio
async def test_daemon_handles_failed_jobs():
    results = [make_result(success=False, job_id="bad-job"), None]
    orchestrator = MagicMock()
    orchestrator.process_next = AsyncMock(side_effect=results)

    daemon = WorkerDaemon(orchestrator=orchestrator, max_jobs=1, idle_timeout=0.3)
    count = await daemon.run()
    assert count == 1


@pytest.mark.asyncio
async def test_daemon_stop_event_breaks_loop():
    orchestrator = MagicMock()
    call_count = 0

    async def slow_none():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return None

    orchestrator.process_next = slow_none

    daemon = WorkerDaemon(orchestrator=orchestrator)

    async def stop_soon():
        await asyncio.sleep(0.2)
        daemon._stop_event.set()

    await asyncio.gather(daemon.run(), stop_soon())
    assert call_count >= 1


@pytest.mark.asyncio
async def test_run_daemon_convenience():
    from workers.daemon import run_daemon

    orchestrator = MagicMock()
    orchestrator.process_next = AsyncMock(return_value=None)

    count = await run_daemon(orchestrator=orchestrator, idle_timeout=0.2)
    assert count == 0
