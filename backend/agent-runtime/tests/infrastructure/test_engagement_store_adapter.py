from __future__ import annotations

import pytest

from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.infrastructure.engagement.memory_store import MemoryEngagementStateStore


@pytest.mark.unit
def test_engagement_store_roundtrip() -> None:
    store = MemoryEngagementStateStore()
    engagement = Engagement(
        id="eng-1",
        tenant_id="default",
        goal="investigate beaconing",
        mode=EngagementMode.ASYNC,
        status=EngagementStatus.CREATED,
        plan_strategy=PlanStrategy.META_LLM,
        correlation_id="eng-1",
    )
    store.upsert(engagement)
    loaded = store.get("default", "eng-1")
    assert loaded is not None
    assert loaded.goal == "investigate beaconing"

    store.update_planner_state(
        "default",
        "eng-1",
        planner_plan=["soc", "network"],
        planner_status="ok",
        planner_rationale="test",
    )
    store.mark_persona_done("default", "eng-1", "soc")
    store.append_finding("default", "eng-1", {"summary": "beacon detected"})
    final = store.get("default", "eng-1")
    assert final is not None
    assert final.planner_plan == ["soc", "network"]
    assert final.completed_personas == ["soc"]
    assert final.findings_summary == [{"summary": "beacon detected"}]
    assert final.status == EngagementStatus.RUNNING

    recent = store.list_recent("default", limit=10)
    assert len(recent) == 1
    assert recent[0].id == "eng-1"
