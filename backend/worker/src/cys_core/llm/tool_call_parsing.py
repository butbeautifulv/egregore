from __future__ import annotations

import json
from typing import Any

from cys_core.domain.parsing.json_text import parse_json_text


def normalize_tool_call_id(raw: Any, *, index: int = 0) -> str:
    """Return a non-empty tool_call_id (LangChain rejects None)."""
    text = str(raw or "").strip()
    return text or f"call_{index}"


def tool_call_id_from_mapping(call: Any, *, index: int = 0) -> str:
    if isinstance(call, dict):
        raw = call.get("id", call.get("tool_call_id"))
    else:
        raw = getattr(call, "id", None) or getattr(call, "tool_call_id", None)
    return normalize_tool_call_id(raw, index=index)


def stream_tool_call_index(item: Any, *, fallback: int) -> int:
    if isinstance(item, dict):
        idx = item.get("index")
    else:
        idx = getattr(item, "index", None)
    return int(idx) if idx is not None else fallback


def ensure_unique_tool_call_ids(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for index, call in enumerate(tool_calls):
        call_id = str(call.get("id") or "").strip() or f"call_{index}"
        if call_id in seen:
            suffix = 1
            candidate = f"{call_id}_{suffix}"
            while candidate in seen:
                suffix += 1
                candidate = f"{call_id}_{suffix}"
            call_id = candidate
        seen.add(call_id)
        out.append({**call, "id": call_id})
    return out


def repair_tool_call_ids_in_messages(messages: list[Any]) -> list[Any]:
    """Ensure assistant/tool message pairs use unique tool_call_id values before API round-trips."""
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

    out: list[BaseMessage] = []
    id_slots: dict[str, list[str]] = {}
    slot_cursor: dict[str, int] = {}
    for message in messages:
        if isinstance(message, AIMessage):
            id_slots = {}
            slot_cursor = {}
            if not message.tool_calls:
                out.append(message)
                continue
            fixed_calls: list[dict[str, Any]] = []
            seen: set[str] = set()
            for index, tc in enumerate(message.tool_calls):
                call = dict(tc)
                old_id = str(call.get("id") or "").strip() or f"call_{index}"
                new_id = old_id
                if new_id in seen:
                    suffix = 1
                    candidate = f"{new_id}_{suffix}"
                    while candidate in seen:
                        suffix += 1
                        candidate = f"{new_id}_{suffix}"
                    new_id = candidate
                seen.add(new_id)
                call["id"] = new_id
                fixed_calls.append(call)
                id_slots.setdefault(old_id, []).append(new_id)
            out.append(message.model_copy(update={"tool_calls": fixed_calls}))
            continue
        if isinstance(message, ToolMessage):
            old_tid = message.tool_call_id
            slots = id_slots.get(old_tid, [])
            cursor = slot_cursor.get(old_tid, 0)
            if cursor < len(slots):
                new_tid = slots[cursor]
                slot_cursor[old_tid] = cursor + 1
                if new_tid != old_tid:
                    out.append(message.model_copy(update={"tool_call_id": new_tid}))
                else:
                    out.append(message)
            else:
                out.append(message)
            continue
        id_slots = {}
        slot_cursor = {}
        out.append(message)
    return out


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
            call_id = normalize_tool_call_id(item.get("id"), index=index)
        else:
            fn = getattr(item, "function", None)
            name = getattr(fn, "name", None) if fn else getattr(item, "name", "")
            raw_args = getattr(fn, "arguments", None) if fn else getattr(item, "arguments", None)
            args = parse_tool_call_args(raw_args)
            call_id = normalize_tool_call_id(getattr(item, "id", None), index=index)
        if name:
            out.append({"name": name, "args": args, "id": call_id, "type": "tool_call"})
    return ensure_unique_tool_call_ids(out)


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
                "id": normalize_tool_call_id(item.get("id"), index=index),
                "type": "tool_call",
            }
        )
    return ensure_unique_tool_call_ids(out)
