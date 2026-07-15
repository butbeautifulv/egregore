from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.enqueue_follow_up import EnqueueFollowUp, FollowUpError
from cys_core.domain.engagement.models import Engagement, EngagementStatus, SynthesisStatus
from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.infrastructure.memory.stores import InMemoryEpisodicMemoryStore


def _closed_engagement() -> Engagement:
    return Engagement(
        id="eng-closed",
        tenant_id="default",
        goal="done",
        status=EngagementStatus.CLOSED,
        synthesis_status=SynthesisStatus.DONE,
    )


@pytest.mark.unit
def test_enqueue_follow_up_rejects_open_engagement() -> None:
    store = MagicMock()
    store.get.return_value = Engagement(
        id="eng-open",
        tenant_id="default",
        goal="running",
        status=EngagementStatus.RUNNING,
        synthesis_status=SynthesisStatus.DONE,
    )
    use_case = EnqueueFollowUp(
        engagement_store=store,
        memory_writer=MagicMock(),
        memory_reader=MagicMock(),
        job_store=MagicMock(),
        queue=MagicMock(),
    )
    with pytest.raises(FollowUpError) as exc:
        use_case.execute(tenant_id="default", engagement_id="eng-open", message="why?")
    assert exc.value.status_code == 409


@pytest.mark.unit
def test_enqueue_follow_up_queues_consultant_job() -> None:
    episodic = InMemoryEpisodicMemoryStore()
    memory_writer = MemoryWriteService(episodic)
    memory_reader = MemoryReadService(episodic)
    engagement_store = MagicMock()
    engagement_store.get.return_value = _closed_engagement()
    job_store = MagicMock()
    job_store.list_by_investigation.return_value = []
    queue = MagicMock()
    use_case = EnqueueFollowUp(
        engagement_store=engagement_store,
        memory_writer=memory_writer,
        memory_reader=memory_reader,
        job_store=job_store,
        queue=queue,
    )
    result = use_case.execute(
        tenant_id="default",
        engagement_id="eng-closed",
        message="Explain the timeline",
        mode="qa",
    )
    assert result["status"] == "queued"
    assert result["work_kind"] == "follow_up_qa"
    assert result["job_id"].startswith("consultant-fu-")
    queue.enqueue.assert_called_once()
    turns = use_case.list_turns("default", "eng-closed")
    # list_turns() always synthesizes an "operator" turn from engagement.goal
    # (follow_up_id=initial_follow_up_id(...)="wo-eng-closed") when no real memory entry
    # carries that id — persist_operator_turn() only ever mints fresh "fu-<uuid>" ids, so
    # this synthetic turn is a standing feature (shows the original goal as thread context),
    # not a one-time bootstrap fallback. Its created_at is computed fresh at list_turns()
    # call time, i.e. after execute() already persisted the real turn — so it sorts last here.
    assert len(turns) == 2
    assert turns[0]["role"] == "operator"
    assert turns[0]["follow_up_id"] == result["follow_up_id"]
    assert turns[0]["text"] == "Explain the timeline"
    assert turns[1]["role"] == "operator"
    assert turns[1]["follow_up_id"] == "wo-eng-closed"
    assert turns[1]["text"] == "done"
