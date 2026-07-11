from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.enqueue_follow_up import EnqueueFollowUp
from cys_core.application.workers.follow_up_aggregator import FollowUpAggregator
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
        follow_up_spawn_count=2,
        follow_up_spawned_job_ids=["soc-fu-old"],
    )


@pytest.mark.unit
def test_orchestrate_enqueue_resets_spawn_state() -> None:
    episodic = InMemoryEpisodicMemoryStore()
    memory_writer = MemoryWriteService(episodic)
    memory_reader = MemoryReadService(episodic)
    engagement = _closed_engagement()
    engagement_store = MagicMock()
    engagement_store.get.return_value = engagement
    job_store = MagicMock()
    job_store.list_by_investigation.return_value = []
    use_case = EnqueueFollowUp(
        engagement_store=engagement_store,
        memory_writer=memory_writer,
        memory_reader=memory_reader,
        job_store=job_store,
        queue=MagicMock(),
    )

    result = use_case.execute(
        tenant_id="default",
        engagement_id="eng-closed",
        message="reinvestigate lateral movement",
        mode="orchestrate",
    )

    assert result["work_kind"] == "follow_up_orchestrate"
    assert engagement.follow_up_spawn_count == 0
    assert engagement.follow_up_spawned_job_ids == []


@pytest.mark.unit
def test_aggregator_reads_spawned_children_from_engagement() -> None:
    store = MagicMock()
    engagement = Engagement(
        id="eng-1",
        tenant_id="default",
        goal="done",
        follow_up_spawned_job_ids=["soc-fu-a", "intel-fu-b"],
    )
    store.get.return_value = engagement
    aggregator = FollowUpAggregator(MagicMock(), engagement_store=store)

    child_ids = aggregator.spawned_child_ids("default", "eng-1", orchestrator_job_id="conductor-fu-x")

    assert child_ids == ["soc-fu-a", "intel-fu-b"]
