from __future__ import annotations

import pytest

from cys_core.application.use_cases.run_step import RunStep
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.state_models import RunStatus
from cys_core.infrastructure.runs.memory import InMemoryRunStateStore
from cys_core.infrastructure.runs.todo_store import InMemoryWorkTodoStore
from tests.application.port_fakes import run_step_port_kwargs


class _Catalog:
    def list_agents(self, **kwargs):
        return []

    def get_agent(self, name):
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_step_plan_mode_awaits_approval():
    class FakeRuntime:
        async def arun(self, name, user_input, **kwargs):
            return {"plan": {"rationale": "step 1", "proposed_workers": ["soc"], "todos": []}}

    ctx = RunContext.from_session_id("sess-1", mode=InteractionMode.PLAN)
    store = InMemoryRunStateStore()
    step = RunStep(
        runtime=FakeRuntime(),
        state_store=store,
        catalog=_Catalog(),
        todo_store=InMemoryWorkTodoStore(),
        **run_step_port_kwargs(),
    )
    out = await step.execute(ctx, "investigate host")
    assert out["status"] == RunStatus.AWAITING_PLAN_APPROVAL.value
    assert "plan" in out["result"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_step_applies_plan_delta():
    class FakeRuntime:
        async def arun(self, name, user_input, **kwargs):
            assert "todo_snapshot" in user_input
            return {
                "reply": "done step",
                "plan_delta": {"todos": [{"id": "1", "content": "investigate", "status": "done"}]},
            }

    ctx = RunContext.from_session_id("sess-plan", mode=InteractionMode.AGENT)
    store = InMemoryRunStateStore()
    todos = InMemoryWorkTodoStore()
    step = RunStep(
        runtime=FakeRuntime(),
        state_store=store,
        catalog=_Catalog(),
        todo_store=todos,
        **run_step_port_kwargs(),
    )
    await step.execute(ctx, "continue", persona="conductor")
    saved = todos.list_todos(ctx.tenant_id, ctx.context_id)
    assert saved and saved[0].status.value == "done"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_step_trace_rerun_on_low_score(monkeypatch):
    from cys_core.application.use_cases.run_step import RunStep
    from cys_core.domain.runs.models import InteractionMode, RunContext
    from cys_core.domain.runs.trace_models import TraceVerdict
    from cys_core.infrastructure.runs.memory import InMemoryRunStateStore
    from cys_core.infrastructure.runs.todo_store import InMemoryWorkTodoStore

    calls = {"n": 0}

    class FakeRuntime:
        async def arun(self, name, user_input, **kwargs):
            calls["n"] += 1
            return {"reply": f"attempt-{calls['n']}", "plan_delta": {"todos": []}}

    class _Catalog:
        def list_agents(self, **kwargs):
            return []

        def get_agent(self, name):
            return None

    monkeypatch.setattr("cys_core.application.use_cases.run_step.get_task_hints_enabled", lambda: False)
    monkeypatch.setattr("cys_core.application.use_cases.run_step.get_trace_critic_enabled", lambda: True)

    class _FakeResolver:
        def trace_critic_threshold(self, profile_id: str) -> float:
            return 0.55

        def trace_critic_every_n(self, profile_id: str) -> int:
            return 1

        def trace_critic_rerun_max(self, profile_id: str) -> int:
            return 1

        def policy(self, profile_id: str):
            from cys_core.domain.catalog.models import ProfilePolicyPayload, TraceCriticPolicy

            return ProfilePolicyPayload(trace_critic=TraceCriticPolicy(every_n_steps=1, rerun_max=1))

    monkeypatch.setattr(
        "cys_core.application.use_cases.run_step.get_profile_policy_resolver",
        lambda: _FakeResolver(),
    )

    class FakeCritic:
        def execute(self, **kwargs):
            if calls["n"] == 1:
                return TraceVerdict(score=0.2, verdict="fail", should_rerun=True, reasoning="fix trace")
            return TraceVerdict(score=0.9, verdict="pass", should_rerun=False)

    ctx = RunContext.from_session_id("sess-rerun", mode=InteractionMode.AGENT)
    step = RunStep(
        runtime=FakeRuntime(),
        state_store=InMemoryRunStateStore(),
        catalog=_Catalog(),
        todo_store=InMemoryWorkTodoStore(),
        **run_step_port_kwargs(),
    )
    step._trace_critic_for = lambda profile_id: FakeCritic()
    out = await step.execute(ctx, "investigate", persona="conductor")
    assert calls["n"] >= 2
    assert out["result"]["reply"].startswith("attempt-")

    captured = {}

    class FakeRuntime:
        async def arun(self, name, user_input, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

    ctx = RunContext.one_shot_job("job-1", mode=InteractionMode.AGENT)
    step = RunStep(
        runtime=FakeRuntime(),
        state_store=InMemoryRunStateStore(),
        catalog=_Catalog(),
        todo_store=InMemoryWorkTodoStore(),
        **run_step_port_kwargs(),
    )
    await step.execute(ctx, "scan", persona="soc")
    assert captured["session_id"] == "worker:soc:job-1"
