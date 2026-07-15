from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.workers.follow_up_publisher import FollowUpAnswerPublisher
from cys_core.domain.engagement.models import Engagement, EngagementStatus, SynthesisStatus
from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore


@pytest.mark.unit
def test_follow_up_publish_cycle_updates_memory_and_egress() -> None:
    episodic = InMemoryEpisodicMemoryStore()
    memory_writer = MemoryWriteService(episodic)
    memory_reader = MemoryReadService(episodic)
    engagement_store = MagicMock()
    engagement_store.get.return_value = Engagement(
        id="eng-1",
        tenant_id="default",
        goal="done",
        status=EngagementStatus.CLOSED,
        synthesis_status=SynthesisStatus.DONE,
    )
    egress = MagicMock()
    publisher = FollowUpAnswerPublisher(
        memory_writer=memory_writer,
        engagement_egress=egress,
        engagement_store=engagement_store,
    )
    job = WorkerJob(
        job_id="consultant-fu-1",
        event_id="eng-1",
        persona="consultant",
        correlation_id="eng-1",
        tenant_id="default",
        payload={
            "phase": "follow_up",
            "work_kind": "follow_up_qa",
            "follow_up_id": "fu-1",
            "operator_message": "Why?",
        },
    )
    memory_writer.append_conversation_turn(
        tenant_id="default",
        investigation_id="eng-1",
        role="operator",
        text="Why?",
        follow_up_id="fu-1",
    )
    text = publisher.publish_success(job=job, result={"answer": "Because."}, investigation_id="eng-1")
    assert text == "Because."
    egress.publish_event.assert_called_once()
    assert egress.publish_event.call_args.args[1] == "follow_up_complete"
    turns = memory_reader.query_conversation_turns("default", "eng-1")
    assert len(turns) == 2
