from __future__ import annotations

"""Shared in-process dedup-count state, split out of cys_core.middleware.tool_dedup_middleware
so dispatcher-side job cleanup (tool_execution_tracker.clear_tool_execution_count, called
unconditionally for every job regardless of execution backend) doesn't need langchain/langgraph
importable just to clear a plain dict. See docs/MICROSERVICES_SPLIT_PLAN.md §1.

Note: once dispatcher and agent-runtime are genuinely separate processes, dispatcher's copy of
this dict is never the one ToolDedupMiddleware actually counts into during a job's tool-calling
loop (that happens in agent-runtime's process) — dispatcher's clear_tool_dedup() call becomes a
harmless no-op on its own always-empty dict at that point, not a crash. Today, with both still
able to run in-process, it's the same shared state it always was.
"""

dedup_counts: dict[str, dict[str, int]] = {}


def clear_tool_dedup(job_id: str) -> None:
    if job_id:
        dedup_counts.pop(job_id, None)
