from __future__ import annotations

import pytest

from cys_core.application.use_cases.run_step import RunStep
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.plan_models import WorkTodo
from cys_core.domain.runs.state_models import RunState, RunStatus
from tests.application.port_fakes import run_step_port_kwargs


class _StateStore:
    def __init__(self) -> None:
        self.states: list[RunState] = []

    def get(self, tenant_id, context_id, kind):
        for s in self.states:
            if (
                s.run_context.tenant_id == tenant_id
                and s.run_context.context_id == context_id
                and s.run_context.kind.value == kind
            ):
                return s
        return None

    def upsert(self, state: RunState) -> None:
        existing = self.get(state.run_context.tenant_id, state.run_context.context_id, state.run_context.kind.value)
        if existing is None:
            self.states.append(state)
        else:
            idx = self.states.index(existing)
            self.states[idx] = state


class _Catalog:
    def list_agents(self, **kwargs):
        return []

    def get_agent(self, name):
        return None


class _TodoStore:
    def __init__(self) -> None:
        self.replaced: list[WorkTodo] = []

    def list_todos(self, tenant_id, context_id):
        return []

    def replace_todos(self, tenant_id, context_id, todos):
        self.replaced = list(todos)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_step_uses_injected_ports():
    class FakeRuntime:
        async def arun(self, name, user_input, **kwargs):
            return {"todos": [{"id": "1", "content": "x", "status": "pending"}]}

    todos = _TodoStore()
    store = _StateStore()
    ctx = RunContext.from_session_id("s1", mode=InteractionMode.AGENT)
    step = RunStep(
        runtime=FakeRuntime(),
        state_store=store,
        catalog=_Catalog(),
        todo_store=todos,
        **run_step_port_kwargs(),
    )
    await step.execute(ctx, "hello")
    assert len(todos.replaced) == 1
    assert store.states[0].status == RunStatus.IN_PROGRESS
