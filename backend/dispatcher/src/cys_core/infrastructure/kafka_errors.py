from __future__ import annotations


class KafkaBrokerUnavailableError(Exception):
    """Kafka broker connection or client start failed."""


class KafkaMessageDecodeError(Exception):
    """Kafka record payload could not be decoded or validated."""


class KafkaPublishError(Exception):
    """Kafka publish operation failed after producer was available."""
