from __future__ import annotations

import uuid

import pytest

from bootstrap.settings import get_settings
from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.infrastructure.engagement.postgres_store import PostgresEngagementStateStore


def _postgres_store() -> PostgresEngagementStateStore | None:
    try:
        return PostgresEngagementStateStore(get_settings().postgres_url)
    except Exception:
        return None


@pytest.mark.unit
def test_append_finding_visible_across_store_instances() -> None:
    store_writer = _postgres_store()
    if store_writer is None:
        pytest.skip("postgres unavailable")
    store_reader = PostgresEngagementStateStore(get_settings().postgres_url)

    engagement_id = f"eng-test-{uuid.uuid4().hex[:12]}"
    tenant_id = "test-tenant"
    store_writer.upsert(
        Engagement(
            id=engagement_id,
            tenant_id=tenant_id,
            goal="shared state smoke",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["consultant"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
        )
    )
    finding = {
        "persona": "consultant",
        "job_id": "job-1",
        "finding": {"summary": "Use endpoint protection", "recommended_actions": ["Deploy EDR"]},
    }
    store_writer.append_finding(tenant_id, engagement_id, finding)

    loaded = store_reader.get(tenant_id, engagement_id)
    assert loaded is not None
    assert len(loaded.findings_summary) == 1
    assert loaded.findings_summary[0]["persona"] == "consultant"
    assert loaded.findings_summary[0]["finding"]["summary"] == "Use endpoint protection"


@pytest.mark.unit
def test_mark_persona_done_visible_across_store_instances() -> None:
    store_writer = _postgres_store()
    if store_writer is None:
        pytest.skip("postgres unavailable")
    store_reader = PostgresEngagementStateStore(get_settings().postgres_url)

    engagement_id = f"eng-test-{uuid.uuid4().hex[:12]}"
    tenant_id = "test-tenant"
    store_writer.upsert(
        Engagement(
            id=engagement_id,
            tenant_id=tenant_id,
            goal="close on consultant",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["consultant"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
        )
    )
    store_writer.mark_persona_done(tenant_id, engagement_id, "consultant")

    loaded = store_reader.get(tenant_id, engagement_id)
    assert loaded is not None
    assert loaded.status == EngagementStatus.CLOSED
    assert loaded.completed_personas == ["consultant"]
