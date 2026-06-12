from __future__ import annotations

import pytest

from cys_core.infrastructure.bus_transport import InMemoryBusTransport, RedisBusTransport, reset_bus_transport_cache
from cys_core.infrastructure.kafka_bus import KafkaBusTransport
from cys_core.infrastructure.kafka_queue import KafkaJobQueue
from cys_core.infrastructure.queue import RedisJobQueue, reset_job_queue_cache


@pytest.mark.unit
def test_get_job_queue_redis_by_default(monkeypatch):
    from bootstrap.settings import get_settings

    get_settings.cache_clear()
    reset_job_queue_cache()
    monkeypatch.setenv("USE_KAFKA", "false")
    try:
        from cys_core.infrastructure.queue import get_job_queue

        queue = get_job_queue()
        assert isinstance(queue, RedisJobQueue)
    finally:
        get_settings.cache_clear()
        reset_job_queue_cache()


@pytest.mark.unit
def test_get_job_queue_kafka_when_enabled(monkeypatch):
    from bootstrap.settings import get_settings

    get_settings.cache_clear()
    reset_job_queue_cache()
    monkeypatch.setenv("USE_KAFKA", "true")
    try:
        from bootstrap.settings import settings

        settings.use_kafka = True
        from cys_core.infrastructure.queue import get_job_queue

        queue = get_job_queue(persona="soc")
        assert isinstance(queue, KafkaJobQueue)
        assert queue._persona == "soc"
    finally:
        from bootstrap.settings import settings

        settings.use_kafka = False
        get_settings.cache_clear()
        reset_job_queue_cache()


@pytest.mark.unit
def test_get_bus_transport_kafka_when_enabled(monkeypatch):
    from bootstrap.settings import get_settings

    get_settings.cache_clear()
    reset_bus_transport_cache()
    monkeypatch.setenv("USE_KAFKA", "true")
    try:
        from bootstrap.settings import settings

        settings.use_kafka = True
        from cys_core.infrastructure.bus_transport import get_bus_transport

        bus = get_bus_transport()
        assert isinstance(bus, KafkaBusTransport)
    finally:
        from bootstrap.settings import settings

        settings.use_kafka = False
        get_settings.cache_clear()
        reset_bus_transport_cache()


@pytest.mark.unit
def test_get_bus_transport_redis_by_default(monkeypatch):
    from bootstrap.settings import get_settings, settings

    get_settings.cache_clear()
    reset_bus_transport_cache()
    monkeypatch.setenv("USE_KAFKA", "false")
    settings.use_kafka = False
    try:
        from cys_core.infrastructure.bus_transport import get_bus_transport

        bus = get_bus_transport()
        assert isinstance(bus, (RedisBusTransport, InMemoryBusTransport))
    finally:
        settings.use_kafka = False
        get_settings.cache_clear()
        reset_bus_transport_cache()
