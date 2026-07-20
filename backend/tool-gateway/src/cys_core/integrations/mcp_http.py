from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx
import structlog

from cys_core.infrastructure.http_client import async_http_client, sync_http_client

logger = structlog.get_logger(__name__)

T = TypeVar("T")

_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


def _is_transient_http_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return True
    return False


def _backoff_delay_seconds(attempt: int) -> float:
    # Jittered exponential backoff: 0.25-0.5s, 0.5-1s, 1-2s, capped at 4-8s.
    return min(8.0, 0.25 * (2**attempt)) * (1.0 + random.random())


def call_with_retry(fn: Callable[[], T], *, max_retries: int, source: str) -> T:
    """Retry fn() on transient MCP/HTTP failures (timeout, connection error, or
    408/409/429/5xx) with jittered exponential backoff. Everything else (other
    4xx, malformed JSON, arbitrary application exceptions) propagates on the
    first attempt — retrying those can't help. docs/MSP_BACKLOG.md
    §24: every MCP client call used to be single-shot — one dropped connection
    aborted the tool call outright instead of transparently recovering."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_retries or not _is_transient_http_error(exc):
                raise
            delay = _backoff_delay_seconds(attempt)
            logger.warning(
                "mcp_call_retrying",
                source=source,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_s=round(delay, 2),
                error=str(exc),
            )
            time.sleep(delay)
            attempt += 1


async def acall_with_retry(fn: Callable[[], Awaitable[T]], *, max_retries: int, source: str) -> T:
    attempt = 0
    while True:
        try:
            return await fn()
        except Exception as exc:
            if attempt >= max_retries or not _is_transient_http_error(exc):
                raise
            delay = _backoff_delay_seconds(attempt)
            logger.warning(
                "mcp_call_retrying",
                source=source,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_s=round(delay, 2),
                error=str(exc),
            )
            await asyncio.sleep(delay)
            attempt += 1


def build_tools_call_payload(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }


def parse_mcp_text_content(result: dict[str, Any]) -> Any:
    text_blocks = [
        block.get("text", "")
        for block in result.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    combined = "\n".join(t for t in text_blocks if t).strip()
    if not combined:
        return combined
    try:
        return json.loads(combined)
    except json.JSONDecodeError:
        return combined


def invoke_mcp_sync(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
    max_retries: int | None = None,
    source: str = "mcp",
) -> dict[str, Any]:
    from cys_core.application.runtime_config import get_mcp_call_max_retries

    def _call() -> dict[str, Any]:
        with sync_http_client(timeout=timeout, headers=headers) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    retries = get_mcp_call_max_retries() if max_retries is None else max_retries
    return call_with_retry(_call, max_retries=retries, source=source)


async def invoke_mcp_async(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
    max_retries: int | None = None,
    source: str = "mcp",
) -> dict[str, Any]:
    from cys_core.application.runtime_config import get_mcp_call_max_retries

    async def _call() -> dict[str, Any]:
        async with async_http_client(timeout=timeout, headers=headers) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    retries = get_mcp_call_max_retries() if max_retries is None else max_retries
    return await acall_with_retry(_call, max_retries=retries, source=source)


def finalize_mcp_result(
    tool_name: str,
    body: dict[str, Any],
    *,
    source: str,
    hint_fn: Callable[[str, str], str] | None = None,
    validation_fn: Callable[[Any], str | None] | None = None,
    on_success: Callable[[str], None] | None = None,
    on_failure: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if "error" in body:
        err = body["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        if on_failure:
            on_failure(tool_name)
        hint = hint_fn(tool_name, message) if hint_fn else ""
        return {"success": False, "error": message + hint, "source": source, "tool": tool_name}

    result = body.get("result") or {}
    parsed = parse_mcp_text_content(result)
    validation_error = validation_fn(parsed) if validation_fn else None
    if validation_error is None and isinstance(parsed, dict):
        nested = parsed.get("content")
        validation_error = validation_fn(nested) if validation_fn else None
    if validation_error is not None:
        if on_failure:
            on_failure(tool_name)
        hint = hint_fn(tool_name, validation_error) if hint_fn else ""
        return {
            "success": False,
            "error": validation_error + hint,
            "source": source,
            "tool": tool_name,
            "content": parsed,
        }

    if on_success:
        on_success(tool_name)
    return {
        "success": True,
        "source": source,
        "tool": tool_name,
        "content": parsed,
        "readonly": True,
    }
