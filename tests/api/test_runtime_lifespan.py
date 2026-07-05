from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from interfaces.api.task_supervisor import BackgroundTaskSupervisor


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fastapi_lifespan_shutdown_cancels_supervisor_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    from interfaces.api.app import create_app

    monkeypatch.setattr("interfaces.api.app.refresh_platform_gauges", lambda: None)
    monkeypatch.setattr("interfaces.api.app.setup_otel", lambda **kwargs: None)
    monkeypatch.setattr("cys_core.observability.logging_setup.configure_logging", lambda *_a, **_k: None)
    monkeypatch.setattr("interfaces.api.app.get_container", lambda: MagicMock(
        get_trace_backend=lambda: MagicMock(flush=MagicMock(), shutdown=MagicMock()),
    ))

    cancelled = asyncio.Event()

    async def _blocking_loop() -> None:
        try:
            while True:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    original_spawn = BackgroundTaskSupervisor.spawn

    def _spawn_and_replace(self, coro, *, name=None):
        if name == "refresh-platform-gauges":
            return original_spawn(self, _blocking_loop(), name=name)
        return original_spawn(self, coro, name=name)

    monkeypatch.setattr(BackgroundTaskSupervisor, "spawn", _spawn_and_replace)

    app = create_app(ingress=MagicMock())
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.1)

    await asyncio.wait_for(cancelled.wait(), timeout=2.0)
