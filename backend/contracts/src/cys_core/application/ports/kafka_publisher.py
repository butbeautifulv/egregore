from __future__ import annotations

from typing import Any, Protocol

from cys_core.application.ports.managed_resource import Closeable


class KafkaPublisherPort(Closeable, Protocol):
    """Port for shared async Kafka event publishing."""

    name: str

    async def publish_bytes(self, topic: str, payload: bytes) -> bool:
        """Publish raw bytes to a Kafka topic."""

    async def publish_json(self, topic: str, payload: dict[str, Any]) -> bool:
        """Publish a JSON document to a Kafka topic."""
