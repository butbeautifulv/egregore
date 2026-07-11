from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import httpx

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 30.0


def default_timeout(
    *,
    total: float | None = None,
    connect: float = DEFAULT_CONNECT_TIMEOUT,
    read: float | None = None,
) -> httpx.Timeout:
    read_timeout = read if read is not None else (total if total is not None else DEFAULT_READ_TIMEOUT)
    return httpx.Timeout(connect=connect, read=read_timeout, write=read_timeout, pool=connect)


@contextmanager
def sync_http_client(
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: Mapping[str, str] | None = None,
    base_url: str = "",
) -> Iterator[httpx.Client]:
    """Create a short-lived sync httpx client with shared timeout defaults."""
    resolved = timeout if isinstance(timeout, httpx.Timeout) else default_timeout(total=timeout)
    with httpx.Client(timeout=resolved, headers=dict(headers or {}), base_url=base_url) as client:
        yield client


@asynccontextmanager
async def async_http_client(
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: Mapping[str, str] | None = None,
    base_url: str = "",
) -> AsyncIterator[httpx.AsyncClient]:
    """Create a short-lived async httpx client with shared timeout defaults."""
    resolved = timeout if isinstance(timeout, httpx.Timeout) else default_timeout(total=timeout)
    async with httpx.AsyncClient(timeout=resolved, headers=dict(headers or {}), base_url=base_url) as client:
        yield client


def request_json(
    method: str,
    url: str,
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: Mapping[str, str] | None = None,
    json: Any | None = None,
    params: Mapping[str, Any] | None = None,
) -> httpx.Response:
    with sync_http_client(timeout=timeout, headers=headers) as client:
        return client.request(method, url, json=json, params=params)
