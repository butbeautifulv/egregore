from __future__ import annotations

import pytest

from cys_core.application.ports import AgentTransportConnector
from cys_core.infrastructure.bus_transport import InMemoryBusTransport


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_bus_conforms_to_port():
    bus: AgentTransportConnector = InMemoryBusTransport()
    received: list[dict] = []

    async def handler(msg: dict) -> None:
        received.append(msg)

    bus.subscribe("critic", handler)
    await bus.publish("critic", {"sender": "soc", "payload": {"event_id": "e1"}})
    assert received[0]["sender"] == "soc"
