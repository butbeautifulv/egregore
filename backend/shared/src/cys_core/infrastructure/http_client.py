from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import httpx


def _connect_timeout() -> float:
    from cys_core.infrastructure.config.infra_settings import get_http_timeouts

    return get_http_timeouts().connect_s


def _read_timeout() -> float:
    from cys_core.infrastructure.config.infra_settings import get_http_timeouts

    return get_http_timeouts().read_s


def default_timeout(
    *,
    total: float | None = None,
    connect: float | None = None,
    read: float | None = None,
) -> httpx.Timeout:
    resolved_connect = connect if connect is not None else _connect_timeout()
    read_timeout = read if read is not None else (total if total is not None else _read_timeout())
    return httpx.Timeout(connect=resolved_connect, read=read_timeout, write=read_timeout, pool=resolved_connect)


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
