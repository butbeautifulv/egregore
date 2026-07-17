from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cys_core.infrastructure.bus_transport import DELIVERY_TOPIC
from cys_core.infrastructure.kafka_bus import KafkaBusTransport


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publish_delivery_delegates_to_publish() -> None:
    transport = KafkaBusTransport(bootstrap_servers="localhost:9092")
    envelope = {"sender": "consultant", "recipient": "critic", "signature": "sig-1"}

    with patch.object(transport, "publish", new_callable=AsyncMock) as publish_mock:
        await transport.publish_delivery(envelope)

    publish_mock.assert_awaited_once()
    channel, stamped = publish_mock.await_args.args
    assert channel == DELIVERY_TOPIC
    assert stamped["sender"] == "consultant"
    assert "_trace_carrier" in stamped


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publish_delivery_falls_back_when_publish_fails() -> None:
    from cys_core.infrastructure.kafka_errors import KafkaPublishError

    transport = KafkaBusTransport(bootstrap_servers="localhost:9092")
    envelope = {"sender": "consultant", "recipient": "critic"}

    with patch.object(transport, "publish", new_callable=AsyncMock, side_effect=KafkaPublishError("down")):
        with patch.object(transport._fallback, "publish_delivery", new_callable=AsyncMock) as fallback_mock:
            await transport.publish_delivery(envelope)

    fallback_mock.assert_awaited_once()
    assert fallback_mock.await_args.args[0]["sender"] == "consultant"
    assert "_trace_carrier" in fallback_mock.await_args.args[0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publish_delivery_with_live_producer() -> None:
    transport = KafkaBusTransport(bootstrap_servers="localhost:9092")
    producer = MagicMock()
    producer.send_and_wait = AsyncMock()
    transport._producer = producer
    transport._connected = True

    await transport.publish_delivery({"sender": "soc", "recipient": "critic"})

    producer.send_and_wait.assert_awaited_once()
    payload = producer.send_and_wait.await_args.args[1]
    import json

    decoded = json.loads(payload.decode())
    assert decoded["channel"] == DELIVERY_TOPIC
    assert decoded["sender"] == "soc"
    assert "_trace_carrier" in decoded
