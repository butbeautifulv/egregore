from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.application.workers.pipeline_builder import WorkerPipelineDeps, build_worker_pipeline


def _mock_metrics() -> MagicMock:
    metrics = MagicMock()
    metrics.record_memory_read = MagicMock()
    metrics.record_memory_write = MagicMock()
    metrics.record_sanitizer_block = MagicMock()
    metrics.record_worker_job_failure = MagicMock()
    metrics.record_follow_up_completed = MagicMock()
    metrics.record_follow_up_failed = MagicMock()
    return metrics


def _pipeline_deps(**overrides: object) -> WorkerPipelineDeps:
    defaults = {
        "engagement_store": MagicMock(),
        "memory_reader": MagicMock(),
        "memory_writer": MagicMock(),
        "metrics": _mock_metrics(),
        "runtime": MagicMock(),
        "schema_registry": MagicMock(),
        "bus": MagicMock(),
        "transport": MagicMock(),
        "queue": MagicMock(),
        "job_store": MagicMock(),
        "agent_catalog": MagicMock(),
        "engagement_egress": MagicMock(),
        "bus_guard": MagicMock(),
        "agent_registry": MagicMock(),
        "sandbox": MagicMock(),
        "sanitizer": MagicMock(),
        "worker_tracing": MagicMock(),
        "use_tool_gateway": False,
        "dev_schema_bypass": False,
        "resolve_mcp_tools": MagicMock(),
        "resolve_legacy_tools": MagicMock(return_value=[]),
        "make_load_skill_tool": MagicMock(),
    }
    defaults.update(overrides)
    return WorkerPipelineDeps(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
def test_build_worker_pipeline_returns_run_worker_job() -> None:
    pipeline = build_worker_pipeline(_pipeline_deps())
    assert isinstance(pipeline, RunWorkerJob)


@pytest.mark.unit
def test_build_worker_pipeline_with_follow_up_plan_runner() -> None:
    pipeline = build_worker_pipeline(
        _pipeline_deps(meta_planner=MagicMock(), dispatch=MagicMock()),
    )
    assert isinstance(pipeline, RunWorkerJob)
    assert pipeline._plan_follow_up_runner is not None
