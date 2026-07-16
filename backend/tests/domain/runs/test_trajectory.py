from __future__ import annotations

from cys_core.domain.runs.trajectory import AgentTrajectory, TraceEvent


def test_agent_trajectory_serializes() -> None:
    traj = AgentTrajectory(trajectory_id="t-1", context_id="c-1", persona="soc")
    traj.record(TraceEvent(type="tool", name="web_search", payload={"q": "x"}))

    dumped = traj.model_dump(mode="json")
    loaded = AgentTrajectory.model_validate(dumped)
    assert loaded.events[0].type == "tool"
    assert loaded.events[0].payload["q"] == "x"

