from __future__ import annotations

import json
import threading
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, cast

import structlog

from bootstrap.settings import Settings, get_settings
from cys_core.application.ports.bus import AgentTransportConnector
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import bind_correlation_id, bind_from_carrier, reset_correlation_id, trace_carrier
from cys_core.observability.worker_spans import observability_span

logger = structlog.get_logger(__name__)

DELIVERY_TOPIC = "bus.deliveries"

BusHandler = Callable[[dict[str, Any]], Awaitable[None] | None]

_bus_main_loop: Any = None


def set_bus_main_event_loop(loop: Any) -> None:
    global _bus_main_loop
    _bus_main_loop = loop


def get_bus_main_event_loop() -> Any:
    return _bus_main_loop


class InMemoryBusTransport:
    """In-process bus transport for tests and single-node dev."""

    name = "memory"
    requires_mtls = False

    def __init__(self) -> None:
        self._handlers: dict[str, list[BusHandler]] = defaultdict(list)
        self._messages: list[dict[str, Any]] = []

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        self._messages.append(message)
        return message

    async def send_async(self, message: dict[str, Any]) -> dict[str, Any]:
        return self.send(message)

    def subscribe(self, channel: str, handler: BusHandler) -> None:
        self._handlers[channel].append(handler)

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        stamped = {**message, "_trace_carrier": trace_carrier()}
        with observability_span("bus.publish", channel=channel):
            for handler in self._handlers.get(channel, []):
                result = handler(stamped)
                if hasattr(result, "__await__"):
                    await result

    async def publish_delivery(self, message: dict[str, Any]) -> None:
        stamped = {**message, "_trace_carrier": trace_carrier()}
        with observability_span("bus.publish", channel=DELIVERY_TOPIC):
            self._messages.append(stamped)
            await self.publish(DELIVERY_TOPIC, stamped)

    @property
    def messages(self) -> list[dict[str, Any]]:
        return list(self._messages)


class RedisBusTransport:
    """Redis pub/sub bus transport between worker pods."""

    name = "redis"
    requires_mtls = True
    CHANNEL_PREFIX = "cys:bus:"

    def __init__(self, redis_url: str | None = None, *, settings: Settings | None = None) -> None:
        self._fallback = InMemoryBusTransport()
        self._handlers: dict[str, list[BusHandler]] = defaultdict(list)
        self._redis = None
        self._pubsub: Any = None
        self._subscriber_thread: threading.Thread | None = None
        self._subscriber_channels: set[str] = set()
        self._stop_event = threading.Event()
        cfg = settings or get_settings()
        self._redis_url = redis_url or cfg.redis_url
        self._get_message_timeout_s = cfg.bus_redis_get_message_timeout_s
        self._subscriber_join_timeout_s = cfg.bus_redis_subscriber_join_timeout_s
        try:
            import redis

            self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)
            self._redis.ping()
        except Exception as exc:
            metrics.record_infrastructure_fallback("redis_bus", reason="connect_failed")
            logger.warning("redis_bus_unavailable", redis_url=self._redis_url, error=str(exc))
            self._redis = None

    @property
    def active_backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    def _channel(self, name: str) -> str:
        return f"{self.CHANNEL_PREFIX}{name}"

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        if self._redis is None:
            metrics.record_infrastructure_fallback("redis_bus", reason="publish_fallback")
            return self._fallback.send(message)
        recipient = message.get("recipient", "broadcast")
        self._redis.publish(self._channel(recipient), json.dumps(message, ensure_ascii=False))
        return message

    async def send_async(self, message: dict[str, Any]) -> dict[str, Any]:
        return self.send(message)

    def subscribe(self, channel: str, handler: BusHandler) -> None:
        self._handlers[channel].append(handler)
        if self._redis is not None:
            self._fallback.subscribe(channel, handler)

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        stamped = {**message, "_trace_carrier": trace_carrier()}
        with observability_span("bus.publish", channel=channel):
            if self._redis is not None:
                self._redis.publish(self._channel(channel), json.dumps(stamped, ensure_ascii=False))
            await self._fallback.publish(channel, stamped)

    async def publish_delivery(self, message: dict[str, Any]) -> None:
        stamped = {**message, "_trace_carrier": trace_carrier()}
        with observability_span("bus.publish", channel=DELIVERY_TOPIC):
            if self._redis is not None:
                self._redis.publish(self._channel(DELIVERY_TOPIC), json.dumps(stamped, ensure_ascii=False))
            await self._fallback.publish_delivery(stamped)

    def _run_async_handler(self, channel: str, coro: Awaitable[None]) -> None:
        import asyncio

        main_loop = get_bus_main_event_loop()
        if main_loop is not None:
            try:
                future = asyncio.run_coroutine_threadsafe(cast(Coroutine[Any, Any, None], coro), main_loop)
                future.result(timeout=60)
            except Exception as exc:
                metrics.record_infrastructure_fallback("redis_bus", reason="handler_failed")
                logger.exception(
                    "redis_bus_async_handler_failed",
                    channel=channel,
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            try:
                asyncio.run(cast(Coroutine[Any, Any, None], coro))
            except Exception as exc:
                metrics.record_infrastructure_fallback("redis_bus", reason="handler_failed")
                logger.exception(
                    "redis_bus_async_handler_failed",
                    channel=channel,
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
            return
        logger.warning(
            "redis_bus_async_handler_skipped",
            channel=channel,
            reason="running_event_loop_from_subscriber_thread",
        )
        from cys_core.application.runtime_config import get_stage

        if get_stage() == "prod":
            logger.error(
                "redis_bus_main_loop_not_set",
                channel=channel,
                hint="call wire_async_bus() during process startup",
            )

    def _dispatch_message(self, channel: str, message: dict[str, Any]) -> None:
        carrier = message.get("_trace_carrier")
        carrier_token = bind_from_carrier(carrier) if isinstance(carrier, dict) else None
        correlation_id = str(message.get("correlation_id") or message.get("investigation_id") or "")
        token = bind_correlation_id(correlation_id) if correlation_id else None
        try:
            with observability_span("bus.consume", channel=channel):
                for handler in self._handlers.get(channel, []):
                    try:
                        result = handler(message)
                        if hasattr(result, "__await__"):
                            self._run_async_handler(channel, result)
                    except Exception as exc:
                        metrics.record_infrastructure_fallback("redis_bus", reason="handler_failed")
                        logger.exception(
                            "redis_bus_handler_failed",
                            channel=channel,
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )
        finally:
            if token is not None:
                reset_correlation_id(token)
            if carrier_token is not None:
                reset_correlation_id(carrier_token)

    def start_subscriber_loop(self, channels: list[str] | None = None) -> None:
        if self._redis is None or self._subscriber_thread is not None:
            return
        wanted = set(channels or list(self._handlers))
        if not wanted:
            return
        self._subscriber_channels = wanted
        self._stop_event.clear()

        def _listen() -> None:
            redis = self._redis
            if redis is None:
                return
            pubsub = redis.pubsub(ignore_subscribe_messages=True)
            self._pubsub = pubsub
            for channel in self._subscriber_channels:
                pubsub.subscribe(self._channel(channel))
            while not self._stop_event.is_set():
                message = pubsub.get_message(timeout=self._get_message_timeout_s)
                if not message or message.get("type") != "message":
                    continue
                raw_channel = str(message.get("channel", ""))
                channel_name = raw_channel.removeprefix(self.CHANNEL_PREFIX)
                try:
                    payload = json.loads(message.get("data", "{}"))
                except json.JSONDecodeError:
                    continue
                self._dispatch_message(channel_name, payload)
            pubsub.close()

        self._subscriber_thread = threading.Thread(target=_listen, name="redis-bus-subscriber", daemon=True)
        self._subscriber_thread.start()

    async def aclose(self) -> None:
        self._stop_event.set()
        if self._subscriber_thread is not None:
            self._subscriber_thread.join(timeout=self._subscriber_join_timeout_s)
            self._subscriber_thread = None
        if self._pubsub is not None:
            try:
                self._pubsub.close()
            except Exception as exc:
                logger.warning("redis_bus_pubsub_close_failed", error=str(exc))
            self._pubsub = None
        if self._redis is not None:
            try:
                self._redis.close()
            except Exception as exc:
                logger.warning("redis_bus_redis_close_failed", error=str(exc))
            self._redis = None


_bus_transport: AgentTransportConnector | None = None


def get_bus_transport(
    *,
    settings: Settings | None = None,
) -> AgentTransportConnector:
    """Return bus transport connector; Kafka when USE_KAFKA=true."""
    global _bus_transport
    cfg = settings or get_settings()
    if _bus_transport is not None and settings is None:
        return _bus_transport
    transport: AgentTransportConnector
    if cfg.use_kafka:
        from cys_core.infrastructure.kafka_bus import KafkaBusTransport

        transport = KafkaBusTransport(settings=cfg)
    else:
        transport = RedisBusTransport(settings=cfg)
    if settings is None:
        _bus_transport = transport
    return transport


def reset_bus_transport_cache() -> None:
    """Clear cached bus transport (tests)."""
    global _bus_transport
    _bus_transport = None
