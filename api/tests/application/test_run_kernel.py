from __future__ import annotations

from typing import Any

import pytest

from cys_core.application.runs.agent_run_kernel import AgentRunKernel
from cys_core.application.runs.kernel_mappers import (
    new_trajectory,
    run_state_to_kernel_request,
    worker_job_to_kernel_request,
)
from cys_core.application.runs.kernel_memory import record_memory_write
from cys_core.application.runs.kernel_tool_capture import capture_tool_traces
from cys_core.domain.runs.kernel_models import RunKernelMode
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.state_models import RunState
from cys_core.domain.workers.models import WorkerJob


class _StubRuntime:
    async def arun(self, name: str, user_input: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "answer": "ok",
            "reasoning_steps": [
                {"tool": "search", "args": {"q": "test"}, "latency_ms": 12.5},
            ],
        }


@pytest.mark.unit
def test_run_state_maps_to_interactive_kernel_request() -> None:
    ctx = RunContext.from_session_id("sess-1", profile_id="general-assistant", mode=InteractionMode.AGENT)
    state = RunState(run_context=ctx, goal="investigate")
    request = run_state_to_kernel_request(
        state=state,
        ctx=ctx,
        user_input="hello",
        persona="conductor",
        prompt="prompt body",
    )
    assert request.mode == RunKernelMode.INTERACTIVE
    assert request.persona == "conductor"
    assert request.profile_id == "general-assistant"
    assert request.session_id == "run:session:sess-1"


@pytest.mark.unit
def test_worker_job_maps_to_worker_kernel_request() -> None:
    job = WorkerJob(
        job_id="job-1",
        event_id="evt-1",
        persona="consultant",
        correlation_id="inv-1",
        payload={"profile_id": "general-assistant"},
    )
    request = worker_job_to_kernel_request(
        job,
        prompt='{"task": true}',
        session_id="worker:consultant:job-1",
        profile_id="general-assistant",
        memory_entries_loaded=3,
    )
    assert request.mode == RunKernelMode.WORKER
    assert request.run_id == "job-1"
    assert request.memory_entries_loaded == 3
    assert request.max_tokens > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_run_kernel_captures_trajectory() -> None:
    job = WorkerJob(job_id="job-2", event_id="evt-2", persona="consultant", correlation_id="inv-2")
    request = worker_job_to_kernel_request(
        job,
        prompt="run",
        session_id="worker:consultant:job-2",
        profile_id="general-assistant",
        memory_entries_loaded=2,
    )
    result = await AgentRunKernel(_StubRuntime()).execute(request)
    assert result.success is True
    types = {event.type for event in result.trajectory.events}
    assert "memory" in types
    assert "model" in types
    assert "tool" in types


@pytest.mark.unit
def test_interactive_and_worker_share_trajectory_schema() -> None:
    """Smoke: both paths produce AgentTrajectory with the same core fields."""
    ctx = RunContext.from_session_id("sess-smoke", profile_id="cybersec-soc")
    state = RunState(run_context=ctx, goal="g")
    interactive = run_state_to_kernel_request(
        state=state,
        ctx=ctx,
        user_input="u",
        persona="conductor",
        prompt="p",
    )
    job = WorkerJob(job_id="j-smoke", event_id="e", persona="consultant", correlation_id="inv")
    worker = worker_job_to_kernel_request(
        job,
        prompt="p",
        session_id="worker:consultant:j-smoke",
        profile_id="cybersec-soc",
    )
    traj_i = new_trajectory(interactive)
    traj_w = new_trajectory(worker)
    record_memory_write(traj_i, interactive, memory_type="finding", size=10)
    capture_tool_traces({"reasoning_steps": [{"tool": "t", "args": {}}]}, traj_w)
    shared_keys = {
        "trajectory_id",
        "context_id",
        "tenant_id",
        "profile_id",
        "persona",
        "correlation_id",
        "run_id",
        "events",
    }
    assert shared_keys <= set(traj_i.model_dump().keys())
    assert shared_keys <= set(traj_w.model_dump().keys())
