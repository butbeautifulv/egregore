from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore
from tests.application.workers.factory import build_run_worker_job_for_tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_second_worker_receives_first_worker_memory_context():
    episodic = InMemoryEpisodicMemoryStore()
    writer = MemoryWriteService(episodic)
    reader = MemoryReadService(episodic)

    writer.append_finding(
        tenant_id="tenant-a",
        investigation_id="inv-shared",
        source_agent="soc",
        source_job_id="job-soc",
        finding={"summary": "Suspicious login from host beacon-alpha", "confidence": 0.95},
        trust_score=0.95,
    )

    captured_input: dict[str, str] = {}

    class FakeRuntime:
        async def arun(self, name, user_input, **kwargs):
            captured_input["text"] = user_input
            captured_input["investigation_id"] = kwargs.get("investigation_id", "")
            return {"summary": "network follow-up"}

    bus = SimpleNamespace(
        send_message=lambda *args, **kwargs: {"payload": kwargs},
        receive_message=lambda *_a, **_k: None,
        record_agent_failure=lambda *_a, **_k: None,
    )
    sandbox = SimpleNamespace(
        acreate=AsyncMock(return_value=SimpleNamespace(sandbox_id="sb-1")),
        adestroy=AsyncMock(),
    )
    transport = SimpleNamespace(publish_delivery=AsyncMock())
    queue = SimpleNamespace(send_to_dlq=None)
    registry = SimpleNamespace(get=lambda _name: SimpleNamespace(tools=[], skills=[], schema_name=None))

    use_case = build_run_worker_job_for_tests(
        runtime=FakeRuntime(),
        registry=registry,
        bus=bus,
        sandbox=sandbox,
        transport=transport,
        queue=queue,
        memory_reader=reader,
    )

    job = WorkerJob(
        job_id="job-network",
        event_id="evt-1",
        persona="network",
        correlation_id="inv-shared",
        tenant_id="tenant-a",
    )
    await use_case.execute(job, job, "worker:network:job-network", {"status": "success"})

    assert "prior_findings" in captured_input["text"]
    assert "beacon-alpha" in captured_input["text"]
    assert captured_input["investigation_id"] == "inv-shared"
