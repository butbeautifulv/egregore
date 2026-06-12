from __future__ import annotations

import pytest

from cys_core.infrastructure.kafka_bus import KafkaBusTransport


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_bus_publish_falls_back_to_memory():
    bus = KafkaBusTransport(bootstrap_servers="127.0.0.1:1")
    received: list[dict] = []

    async def handler(msg: dict) -> None:
        received.append(msg)

    bus.subscribe("critic", handler)
    await bus.publish("critic", {"sender": "soc", "type": "finding"})
    assert len(received) == 1
    assert received[0]["channel"] == "critic"


@pytest.mark.unit
def test_kafka_bus_send_sync():
    bus = KafkaBusTransport(bootstrap_servers="127.0.0.1:1")
    msg = bus.send({"recipient": "critic", "type": "finding"})
    assert msg["type"] == "finding"
