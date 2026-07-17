from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.enqueue_follow_up import EnqueueFollowUp
from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy


@pytest.mark.unit
def test_list_turns_synthetic_initial_from_goal() -> None:
    engagement = Engagement(
        id="eng-legacy123456",
        goal="Legacy goal text",
        mode=EngagementMode.ASYNC,
        status=EngagementStatus.CLOSED,
        plan_strategy=PlanStrategy.META_LLM,
    )
    memory_reader = MagicMock()
    memory_reader.query_conversation_turns.return_value = []
    engagement_store = MagicMock()
    engagement_store.get.return_value = engagement
    use_case = EnqueueFollowUp(
        engagement_store=engagement_store,
        memory_writer=MagicMock(),
        memory_reader=memory_reader,
        job_store=MagicMock(),
        queue=MagicMock(),
    )
    turns = use_case.list_turns("default", "eng-legacy123456")
    assert len(turns) == 1
    assert turns[0]["follow_up_id"] == "wo-eng-legacy123456"
    assert turns[0]["text"] == "Legacy goal text"
    assert turns[0]["role"] == "operator"
