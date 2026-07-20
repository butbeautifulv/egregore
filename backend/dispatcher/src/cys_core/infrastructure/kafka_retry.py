from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")

_DEFAULT_MAX_RETRIES = 2


async def start_with_retry(
    build_and_start: Callable[[], Awaitable[T]], *, max_retries: int = _DEFAULT_MAX_RETRIES, source: str
) -> T:
    """Retry an AIOKafkaProducer/AIOKafkaConsumer construct+start with jittered backoff.

    Every Kafka producer/consumer construction site tried once, no retry — a broker restart
    or brief network blip failed the very next publish/consume outright, same gap Postgres
    (§32) and Redis (§33) had before their own connect_with_retry additions. `build_and_start`
    is expected to raise broadly (aiokafka doesn't have one narrow connection-error type, and
    every existing call site already caught `Exception` this broadly before this helper
    existed) — anything it raises after the retry budget is exhausted propagates unchanged.
    docs/MSP_BACKLOG.md §24.4 point 4/§36."""
    attempt = 0
    while True:
        try:
            return await build_and_start()
        except Exception as exc:
            if attempt >= max_retries:
                raise
            delay = min(4.0, 0.25 * (2**attempt)) * (1.0 + random.random())
            logger.warning(
                "kafka_connect_retrying",
                source=source,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_s=round(delay, 2),
                error=str(exc),
            )
            await asyncio.sleep(delay)
            attempt += 1
