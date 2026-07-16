from __future__ import annotations

from cys_core.infrastructure.kafka_errors import (
    KafkaBrokerUnavailableError,
    KafkaMessageDecodeError,
    KafkaPublishError,
)

__all__ = [
    "InfrastructureError",
    "KafkaBrokerUnavailableError",
    "KafkaMessageDecodeError",
    "KafkaPublishError",
    "RedisUnavailableError",
]


class InfrastructureError(Exception):
    """Base class for infrastructure adapter failures."""


class RedisUnavailableError(InfrastructureError):
    """Redis connection or command failed."""
