from __future__ import annotations

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage


def _tool_call_ids(message: AIMessage) -> list[str]:
    tool_calls = getattr(message, "tool_calls", None) or []
    ids: list[str] = []
    for index, call in enumerate(tool_calls):
        if isinstance(call, dict):
            call_id = str(call.get("id") or call.get("tool_call_id") or f"call_{index}")
        else:
            call_id = str(getattr(call, "id", None) or getattr(call, "tool_call_id", None) or f"call_{index}")
        ids.append(call_id)
    return ids


def _is_tool_turn_start(message: AnyMessage) -> bool:
    return isinstance(message, AIMessage) and bool(_tool_call_ids(message))


def _tool_turn_span(messages: list[AnyMessage], start: int) -> tuple[int, int]:
    """Return [start, end) indices for AIMessage tool_calls + following ToolMessages."""
    if start >= len(messages) or not _is_tool_turn_start(messages[start]):
        return start, start
    expected_ids = set(_tool_call_ids(messages[start]))  # type: ignore[arg-type]
    end = start + 1
    seen: set[str] = set()
    while end < len(messages) and isinstance(messages[end], ToolMessage):
        tool_id = str(getattr(messages[end], "tool_call_id", "") or "")
        if tool_id:
            seen.add(tool_id)
        end += 1
        if expected_ids and seen >= expected_ids:
            break
    return start, end


def _collect_tool_turns(messages: list[AnyMessage]) -> list[tuple[int, int]]:
    turns: list[tuple[int, int]] = []
    index = 0
    while index < len(messages):
        if _is_tool_turn_start(messages[index]):
            start, end = _tool_turn_span(messages, index)
            if end > start:
                turns.append((start, end))
                index = end
                continue
        index += 1
    return turns


def _drop_incomplete_tool_turns(messages: list[AnyMessage]) -> list[AnyMessage]:
    if not messages:
        return messages
    result: list[AnyMessage] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if not _is_tool_turn_start(message):
            result.append(message)
            index += 1
            continue
        start, end = _tool_turn_span(messages, index)
        expected_ids = set(_tool_call_ids(message))  # type: ignore[arg-type]
        tool_ids = {
            str(getattr(messages[pos], "tool_call_id", "") or "")
            for pos in range(start + 1, end)
            if isinstance(messages[pos], ToolMessage)
        }
        tool_ids.discard("")
        if expected_ids and tool_ids >= expected_ids:
            result.extend(messages[start:end])
        index = end if end > start else index + 1
    return result


def trim_tool_results(messages: list[AnyMessage], *, keep: int = 3) -> list[AnyMessage]:
    """Keep the last N complete assistant tool-call turns (AIMessage + ToolMessages)."""
    if keep <= 0:
        return heal_orphaned_tool_messages(messages)
    turns = _collect_tool_turns(messages)
    if len(turns) <= keep:
        return heal_orphaned_tool_messages(_drop_incomplete_tool_turns(messages))
    drop_ranges = turns[: len(turns) - keep]
    drop_indices = {index for start, end in drop_ranges for index in range(start, end)}
    trimmed = [msg for index, msg in enumerate(messages) if index not in drop_indices]
    return heal_orphaned_tool_messages(_drop_incomplete_tool_turns(trimmed))


def heal_orphaned_tool_messages(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Drop leading orphans and incomplete assistant tool-call turns."""
    trimmed = list(messages)
    while trimmed:
        first = trimmed[0]
        if isinstance(first, ToolMessage):
            trimmed.pop(0)
            continue
        role = getattr(first, "type", "") or getattr(first, "role", "")
        content = getattr(first, "content", "")
        if role == "tool":
            trimmed.pop(0)
            continue
        if role == "user" and isinstance(content, list):
            if any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content):
                trimmed.pop(0)
                continue
        break
    return _drop_incomplete_tool_turns(trimmed)
