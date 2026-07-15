from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from cys_core.infrastructure.http_client import async_http_client, sync_http_client


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
) -> dict[str, Any]:
    with sync_http_client(timeout=timeout, headers=headers) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def invoke_mcp_async(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    async with async_http_client(timeout=timeout, headers=headers) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


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
