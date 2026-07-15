from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.domain.workers.models import WorkerJob
from cys_core.registry.schemas import schema_registry
from tests.application.workers.factory import build_run_worker_job_for_tests


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_soc_finding_fails_job() -> None:
    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "summary": "",
                "confidence": 0,
                "recommended_actions": [],
            }
        )
    )
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="SocFinding",
            tools=[],
            skills=[],
            bus_recipients=[],
        )
    )
    job_store = MagicMock()
    runner = build_run_worker_job_for_tests(
        runtime=runtime,
        registry=registry,
        job_store=job_store,
    )
    runner._result_validator._schema_registry = SimpleNamespace(
        get=lambda name: schema_registry.get("SocFinding")
    )
    job = WorkerJob(job_id="soc-evt-1-aaa", event_id="evt-1", persona="soc", correlation_id="inv-1")

    result = await runner.execute(job, job, "worker:soc:soc-evt-1-aaa", {})

    assert result.success is False
    job_store.mark_failed.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_nonempty_soc_finding_completes_job() -> None:
    runtime = SimpleNamespace(arun=AsyncMock(return_value={"summary": "Suspicious activity on host"}))
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="SocFinding",
            tools=[],
            skills=[],
            bus_recipients=[],
        )
    )
    job_store = MagicMock()
    runner = build_run_worker_job_for_tests(
        runtime=runtime,
        registry=registry,
        job_store=job_store,
    )
    runner._result_validator._schema_registry = SimpleNamespace(
        get=lambda name: schema_registry.get("SocFinding")
    )
    job = WorkerJob(job_id="soc-evt-2-bbb", event_id="evt-2", persona="soc", correlation_id="inv-2")

    result = await runner.execute(job, job, "worker:soc:soc-evt-2-bbb", {})

    assert result.success is True
    job_store.mark_completed.assert_called_once()
