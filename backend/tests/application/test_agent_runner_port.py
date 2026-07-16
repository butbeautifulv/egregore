from __future__ import annotations

from typing import Any

import pytest

from cys_core.application.ports import AgentRunner


class _FakeRunner:
    async def arun(self, name: str, user_input: str, **kwargs: Any) -> dict[str, Any]:
        return {"name": name, "input": user_input}

    async def aresume(self, name: str, session_id: str, resume: dict[str, Any]) -> dict[str, Any]:
        return {"resumed": True}


@pytest.mark.unit
def test_agent_runner_protocol():
    runner: AgentRunner = _FakeRunner()
    assert runner is not None
