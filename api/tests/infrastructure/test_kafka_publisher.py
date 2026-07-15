from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cys_core.domain.events.models import SecurityEvent
from cys_core.infrastructure.kafka_publisher import KafkaPublisher, reset_kafka_publisher_cache


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publisher_publish_json_uses_shared_producer() -> None:
    publisher = KafkaPublisher(bootstrap_servers="localhost:19092")
    mock_producer = AsyncMock()
    with patch.object(publisher, "_ensure_producer", return_value=mock_producer):
        ok = await publisher.publish_json("worker.jobs", {"job_id": "j-1"})
    assert ok is True
    mock_producer.send_and_wait.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publisher_aclose_stops_producer() -> None:
    publisher = KafkaPublisher(bootstrap_servers="localhost:19092")
    mock_producer = AsyncMock()
    publisher._producer = mock_producer
    await publisher.aclose()
    mock_producer.stop.assert_awaited_once()
    assert publisher._producer is None


@pytest.mark.unit
def test_reset_kafka_publisher_cache() -> None:
    from cys_core.infrastructure.kafka_publisher import get_kafka_publisher

    first = get_kafka_publisher()
    reset_kafka_publisher_cache()
    second = get_kafka_publisher()
    assert first is not second


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kafka_publisher_injects_correlation_id() -> None:
    from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id

    publisher = KafkaPublisher(bootstrap_servers="localhost:19092")
    captured: dict[str, bytes] = {}

    async def _capture_publish(topic: str, payload: bytes) -> bool:
        captured["payload"] = payload
        return True

    token = bind_correlation_id("inv-42")
    try:
        with patch.object(publisher, "publish_bytes", _capture_publish):
            ok = await publisher.publish_json("security.events.raw", {"event_type": "test"})
    finally:
        reset_correlation_id(token)

    assert ok is True
    import json

    body = json.loads(captured["payload"].decode())
    assert body["correlation_id"] == "inv-42"
