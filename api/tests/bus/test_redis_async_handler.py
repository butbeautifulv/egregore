from __future__ import annotations

import asyncio

import pytest

from cys_core.infrastructure.bus_transport import RedisBusTransport, set_bus_main_event_loop


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_async_handler_uses_main_loop(monkeypatch):
    transport = RedisBusTransport(redis_url="redis://fake")
    transport._redis = None
    seen: list[dict] = []

    async def handler(message: dict) -> None:
        seen.append(message)

    transport.subscribe("bus.deliveries", handler)
    loop = asyncio.get_running_loop()
    set_bus_main_event_loop(loop)
    envelope = {"recipient": "network", "type": "finding", "payload": {"event_id": "e1"}}
    transport._dispatch_message("bus.deliveries", envelope)
    await asyncio.sleep(0.05)
    assert seen == [envelope]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_async_handler_logs_error_when_main_loop_missing_in_prod(monkeypatch):
    monkeypatch.setattr("cys_core.infrastructure.bus_transport.get_bus_main_event_loop", lambda: None)
    monkeypatch.setattr("cys_core.application.runtime_config.get_stage", lambda: "prod")
    logged: list[str] = []
    monkeypatch.setattr(
        "cys_core.infrastructure.bus_transport.logger.error",
        lambda event, **kwargs: logged.append(event),
    )

    transport = RedisBusTransport(redis_url="redis://fake")
    transport._redis = None

    async def handler(_message: dict) -> None:
        pass

    transport._run_async_handler("bus.deliveries", handler({}))
    assert "redis_bus_main_loop_not_set" in logged
