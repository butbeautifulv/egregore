from __future__ import annotations

import json
from typing import Any

from cys_core.domain.parsing.json_text import parse_json_text


def parse_tool_call_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def litellm_tool_calls_to_langchain(tool_calls_raw: Any) -> list[dict[str, Any]]:
    if not tool_calls_raw:
        return []
    out: list[dict[str, Any]] = []
    for index, item in enumerate(tool_calls_raw):
        if isinstance(item, dict):
            fn = item.get("function") or {}
            name = fn.get("name") or item.get("name") or ""
            args = _parse_native_tool_args(fn, item)
            call_id = item.get("id") or f"call_{index}"
        else:
            fn = getattr(item, "function", None)
            name = getattr(fn, "name", None) if fn else getattr(item, "name", "")
            raw_args = getattr(fn, "arguments", None) if fn else getattr(item, "arguments", None)
            args = parse_tool_call_args(raw_args)
            call_id = getattr(item, "id", None) or f"call_{index}"
        if name:
            out.append({"name": name, "args": args, "id": call_id, "type": "tool_call"})
    return out


def _parse_native_tool_args(fn: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    if isinstance(fn, dict):
        return parse_tool_call_args(fn.get("arguments"))
    return parse_tool_call_args(item.get("arguments"))


def tool_calls_from_content(content: str) -> list[dict[str, Any]]:
    """Extract tool_calls planned as JSON inside assistant content (Qwen-style)."""
    parsed = parse_json_text(content)
    if not parsed:
        return []
    raw_calls = parsed.get("tool_calls")
    if not isinstance(raw_calls, list):
        return []
    out: list[dict[str, Any]] = []
    for index, item in enumerate(raw_calls):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("tool_name") or "").strip()
        if not name:
            continue
        args = item.get("arguments") or item.get("tool_arguments") or item.get("args") or {}
        out.append(
            {
                "name": name,
                "args": parse_tool_call_args(args),
                "id": str(item.get("id") or f"call_{index}"),
                "type": "tool_call",
            }
        )
    return out
