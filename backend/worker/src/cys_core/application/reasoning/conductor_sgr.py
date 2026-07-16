from __future__ import annotations

from typing import Any


def filter_spawn_requests_by_sgr(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Drop spawn_requests when SGR signals task is complete or no remaining steps."""
    requests = result.get("spawn_requests") or []
    if not isinstance(requests, list):
        return []
    if result.get("task_completed"):
        return []
    remaining = result.get("remaining_steps") or []
    if isinstance(remaining, list) and len(remaining) == 0 and result.get("enough_data"):
        return []
    return [item for item in requests if isinstance(item, dict)]


def persist_sgr_fields_to_state(state, result: dict[str, Any]) -> None:
    steps = result.get("reasoning_steps")
    if isinstance(steps, list) and steps:
        note = f"sgr: {' | '.join(str(s) for s in steps[:3])}"
        if note not in state.reasoning_notes:
            state.reasoning_notes.append(note)
    if result.get("plan_status"):
        state.last_result["sgr_plan_status"] = result.get("plan_status")
    if "enough_data" in result:
        state.last_result["sgr_enough_data"] = result.get("enough_data")
