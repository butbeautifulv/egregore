from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cys_core.infrastructure.kafka_bus import KafkaBusTransport
from cys_core.infrastructure.kafka_errors import KafkaBrokerUnavailableError, KafkaPublishError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_bus_publish_uses_fallback_when_broker_unavailable() -> None:
    transport = KafkaBusTransport(bootstrap_servers="localhost:19092")
    received: list[dict] = []
    transport._fallback.subscribe("critic", lambda msg: received.append(msg))
    with patch.object(transport, "_ensure_producer", side_effect=KafkaBrokerUnavailableError("down")):
        await transport.publish("critic", {"sender": "soc", "type": "finding"})
    assert len(received) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_bus_aclose_stops_producer() -> None:
    transport = KafkaBusTransport(bootstrap_servers="localhost:19092")
    producer = AsyncMock()
    transport._producer = producer
    transport._connected = True
    await transport.aclose()
    producer.stop.assert_awaited_once()
    assert transport._producer is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_bus_raises_kafka_publish_error_on_send_failure() -> None:
    transport = KafkaBusTransport(bootstrap_servers="localhost:19092")
    producer = AsyncMock()
    producer.send_and_wait.side_effect = RuntimeError("send failed")
    transport._producer = producer
    transport._connected = True
    with patch.object(transport, "_ensure_producer", return_value=True):
        with pytest.raises(KafkaPublishError, match="send failed"):
            await transport.publish("critic", {"sender": "soc"})
