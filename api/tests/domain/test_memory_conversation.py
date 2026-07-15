from __future__ import annotations

import json

import pytest

from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore


@pytest.mark.unit
def test_append_and_query_conversation_turns_in_order() -> None:
    store = InMemoryEpisodicMemoryStore()
    writer = MemoryWriteService(store)
    reader = MemoryReadService(store)

    writer.append_conversation_turn(
        tenant_id="default",
        investigation_id="eng-1",
        role="operator",
        text="What happened?",
        follow_up_id="fu-1",
    )
    writer.append_finding(
        tenant_id="default",
        investigation_id="eng-1",
        source_agent="soc",
        source_job_id="job-soc",
        finding={"summary": "finding"},
        trust_score=0.9,
    )
    writer.append_conversation_turn(
        tenant_id="default",
        investigation_id="eng-1",
        role="assistant",
        text="Here is the answer.",
        follow_up_id="fu-1",
        job_id="consultant-fu-1",
        persona="consultant",
    )

    turns = reader.query_conversation_turns("default", "eng-1", limit=10)
    assert len(turns) == 2
    first = json.loads(turns[0].content)
    second = json.loads(turns[1].content)
    assert first["role"] == "operator"
    assert second["role"] == "assistant"
    assert turns[0].memory_type == "conversation"

    from cys_core.application.workers.context_builder import WorkerContextBuilder
    from cys_core.domain.workers.models import WorkerJob

    builder = WorkerContextBuilder(memory_reader=reader)
    job = WorkerJob(
        job_id="soc-1",
        event_id="eng-1",
        persona="soc",
        correlation_id="eng-1",
        tenant_id="default",
        payload={},
    )
    prior = builder.build(job).get("prior_findings") or []
    assert all(item.get("type") != "conversation" for item in prior)
