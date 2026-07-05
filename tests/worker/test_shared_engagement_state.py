from __future__ import annotations

import uuid

import pytest

from bootstrap.settings import get_settings
from cys_core.domain.engagement.models import Engagement, EngagementMode, EngagementStatus, PlanStrategy
from cys_core.domain.workers.models import WorkerJob
from cys_core.infrastructure.engagement.postgres_store import PostgresEngagementStateStore
from cys_core.infrastructure.engagement.store_factory import get_engagement_state_store, reset_engagement_state_store


def _try_postgres_store() -> PostgresEngagementStateStore | None:
    try:
        return PostgresEngagementStateStore(get_settings().postgres_url)
    except Exception:
        return None


def _delete_engagement(store: PostgresEngagementStateStore, tenant_id: str, engagement_id: str) -> None:
    with store._connect() as conn:
        conn.execute(
            "DELETE FROM engagements WHERE tenant_id = %s AND engagement_id = %s",
            (tenant_id, engagement_id),
        )
        conn.commit()


@pytest.mark.unit
def test_worker_finding_visible_via_shared_postgres_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates API and worker processes sharing engagement state through Postgres."""
    pg_store = _try_postgres_store()
    if pg_store is None:
        pytest.skip("postgres unavailable")

    reset_engagement_state_store()
    monkeypatch.setenv("ENGAGEMENT_STORE_CONNECTOR", "postgres")
    monkeypatch.setenv("STAGE", "dev")
    get_settings.cache_clear()

    worker_store = get_engagement_state_store()
    api_store = get_engagement_state_store()

    # Prefix eng-test-shared- avoids polluting manual ui-minimal smoke (eng-smoke-*).
    engagement_id = f"eng-test-shared-{uuid.uuid4().hex[:12]}"
    tenant_id = "default"
    worker_store.upsert(
        Engagement(
            id=engagement_id,
            tenant_id=tenant_id,
            goal="shared-store integration probe",
            mode=EngagementMode.ASYNC,
            status=EngagementStatus.RUNNING,
            planner_plan=["consultant"],
            planner_status="ok",
            plan_strategy=PlanStrategy.META_LLM,
        )
    )

    from tests.application.workers.factory import build_run_worker_job_for_tests

    job = WorkerJob(
        job_id=f"consultant-{engagement_id}-abc",
        event_id=engagement_id,
        persona="consultant",
        correlation_id=engagement_id,
        tenant_id=tenant_id,
    )
    runner = build_run_worker_job_for_tests(engagement_store=worker_store)
    # Bypass worker gate: append_finding writes directly (not via RunWorkerJob.validate).
    runner._finding_publisher.append_engagement_finding(
        job=job,
        result={
            "topic": "Endpoint protection",
            "summary": "Deploy antivirus and patch regularly",
            "recommendations": ["Enable EDR", "Patch monthly"],
            "references": ["CIS Control 10"],
            "risk_level": "medium",
            "confidence": 0.7,
        },
        investigation_id=engagement_id,
    )
    runner._mark_persona_completed(job)

    try:
        api_view = api_store.get(tenant_id, engagement_id)
        assert api_view is not None
        assert len(api_view.findings_summary) == 1
        assert api_view.findings_summary[0]["finding"]["summary"] == "Deploy antivirus and patch regularly"
        assert api_view.completed_personas == ["consultant"]
        assert api_view.status == EngagementStatus.CLOSED
    finally:
        _delete_engagement(pg_store, tenant_id, engagement_id)
        reset_engagement_state_store()
        get_settings.cache_clear()
