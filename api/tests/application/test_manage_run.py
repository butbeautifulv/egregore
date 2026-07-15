from __future__ import annotations

import pytest

from cys_core.application.use_cases.manage_run import ManageRun
from cys_core.domain.runs.models import InteractionMode, RunContext
from cys_core.domain.runs.state_models import RunStatus
from cys_core.infrastructure.runs.memory import InMemoryRunStateStore
from cys_core.infrastructure.runs.todo_store import InMemoryWorkTodoStore
from tests.application.port_fakes import run_step_port_kwargs


class _Runtime:
    async def arun(self, name, user_input, **kwargs):
        return {"ok": True}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_run_persists_context_in_store():
    store = InMemoryRunStateStore()
    ctx = RunContext.from_session_id("sess-42", mode=InteractionMode.AGENT)
    mgr = ManageRun(
        runtime=_Runtime(),
        state_store=store,
        catalog=type("C", (), {"list_agents": lambda *a, **k: [], "get_agent": lambda *a, **k: None})(),
        todo_store=InMemoryWorkTodoStore(),
        **run_step_port_kwargs(),
    )
    out = await mgr.create_and_step(ctx, "goal")
    loaded = mgr.get_context("sess-42")
    assert loaded.context_id == "sess-42"
    assert out["result"]["ok"] is True
    state = store.get("default", "sess-42", ctx.kind.value)
    assert state is not None
    assert state.status == RunStatus.IN_PROGRESS
