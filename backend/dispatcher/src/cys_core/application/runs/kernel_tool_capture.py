from __future__ import annotations

import hashlib
import json
from typing import Any

from cys_core.domain.runs.trace_models import EvalTraceFields, ToolCallTraceFields, eval_trace, tool_call_trace
from cys_core.domain.runs.trajectory import AgentTrajectory


def _args_digest(args: Any) -> str:
    try:
        blob = json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        blob = str(args)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def capture_tool_traces(output: dict[str, Any], trajectory: AgentTrajectory) -> None:
    """Extract tool-like steps from structured agent output."""
    steps = output.get("reasoning_steps")
    if not isinstance(steps, list):
        return
    for step in steps:
        if not isinstance(step, dict):
            continue
        tool_name = str(step.get("tool") or step.get("tool_name") or step.get("action") or "")
        if not tool_name:
            continue
        trajectory.record(
            tool_call_trace(
                tool_name,
                ToolCallTraceFields(
                    tool=tool_name,
                    args_digest=_args_digest(step.get("args") or step.get("parameters") or {}),
                    success=step.get("error") is None and step.get("status") != "error",
                    latency_ms=float(step.get("latency_ms") or 0.0),
                ),
            )
        )


def capture_eval_trace(
    trajectory: AgentTrajectory,
    *,
    suite: str,
    metric: str,
    score: float,
    verdict: str = "",
) -> None:
    trajectory.record(
        eval_trace(
            suite or "trace_critic",
            EvalTraceFields(suite=suite, metric=metric, score=score, verdict=verdict),
        )
    )
