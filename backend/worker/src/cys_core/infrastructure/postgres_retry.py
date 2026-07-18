from __future__ import annotations

import random
import time
from typing import Any

import psycopg
import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_RETRIES = 2


def connect_with_retry(
    url: str, *, max_retries: int = _DEFAULT_MAX_RETRIES, **connect_kwargs: Any
) -> psycopg.Connection:
    """psycopg.connect() with jittered exponential backoff on transient failures.

    Every store's _connect() used to call psycopg.connect() directly, one shot — a
    Postgres restart or brief network blip failed the very next query with no retry,
    unlike the graceful-degradation paths (falling back to in-memory) that already
    exist elsewhere. docs/MICROSERVICES_SPLIT_PLAN.md §24.4 point 4."""
    attempt = 0
    while True:
        try:
            return psycopg.connect(url, **connect_kwargs)
        except psycopg.OperationalError as exc:
            if attempt >= max_retries:
                raise
            delay = min(4.0, 0.25 * (2**attempt)) * (1.0 + random.random())
            logger.warning(
                "postgres_connect_retrying",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_s=round(delay, 2),
                error=str(exc),
            )
            time.sleep(delay)
            attempt += 1
