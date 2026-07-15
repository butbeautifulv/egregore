from __future__ import annotations

import pytest

from cys_core.application.workers.agent_executor import WorkerAgentExecutor
from cys_core.domain.workers.models import WorkerJob


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_executor_self_refine_max_rounds():
    calls = {"n": 0}

    class Runtime:
        async def arun(self, name, user_input, **kwargs):
            calls["n"] += 1
            if "Critique" in user_input:
                return {"notes": "improve clarity"}
            return {"summary": "revised", "confidence": 0.9}

    executor = WorkerAgentExecutor(runtime=Runtime(), self_refine_max=1)
    job = WorkerJob(job_id="j1", event_id="e1", persona="soc")
    result = await executor.self_refine(job, '{"summary":"draft"}', {"summary": "draft"})
    assert result["summary"] == "revised"
    assert result["self_refine_rounds"] == 1
    assert calls["n"] >= 2
