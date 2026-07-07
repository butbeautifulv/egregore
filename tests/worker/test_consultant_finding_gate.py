from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cys_core.application.workers.finding_quality import (
    consultant_finding_gaps,
    finding_meets_minimum,
    has_planned_tool_calls,
    normalize_consultant_lists,
    normalize_list_field,
)
from cys_core.application.workers.tool_execution_tracker import record_tool_execution
from cys_core.domain.workers.models import WorkerJob
from cys_core.registry.schemas import schema_registry
from tests.application.workers.factory import build_run_worker_job_for_tests


@pytest.mark.unit
def test_normalize_list_field_string_to_list() -> None:
    data = {"recommendations": "Deploy antivirus"}
    normalize_list_field(data, "recommendations")
    assert data["recommendations"] == ["Deploy antivirus"]


@pytest.mark.unit
def test_normalize_list_field_drops_invalid() -> None:
    data = {"recommendations": {"bad": True}}
    normalize_list_field(data, "recommendations")
    assert "recommendations" not in data


@pytest.mark.unit
def test_normalize_recommended_actions_alias() -> None:
    data = {"recommended_actions": ["Enable EDR", "Patch OS"]}
    normalize_consultant_lists(data)
    assert data["recommendations"] == ["Enable EDR", "Patch OS"]


@pytest.mark.unit
def test_recommended_actions_only_still_fails_strict_gate() -> None:
    assert finding_meets_minimum(
        "consultant",
        {"summary": "x", "recommended_actions": ["a", "b"]},
        schema_name="ConsultantFinding",
    ) is False


@pytest.mark.unit
def test_recommended_actions_alias_passes_with_full_fields() -> None:
    assert finding_meets_minimum(
        "consultant",
        {
            "topic": "Malware",
            "summary": "Use EDR",
            "recommended_actions": ["Enable EDR", "Patch monthly"],
            "confidence": 0.8,
        },
        schema_name="ConsultantFinding",
    ) is True


@pytest.mark.unit
def test_consultant_sparse_finding_fails_gate() -> None:
    assert finding_meets_minimum(
        "consultant",
        {"summary": "Deploy antivirus and patch regularly"},
        schema_name="ConsultantFinding",
    ) is False


@pytest.mark.unit
def test_consultant_string_recommendations_only_summary_fails_gate() -> None:
    assert finding_meets_minimum(
        "consultant",
        {"summary": "x", "recommendations": "one only"},
        schema_name="ConsultantFinding",
    ) is False


@pytest.mark.unit
def test_consultant_valid_finding_passes_gate() -> None:
    assert finding_meets_minimum(
        "consultant",
        {
            "topic": "Antivirus strategy",
            "summary": "Deploy layered endpoint protection",
            "recommendations": ["Deploy EDR", "Patch monthly"],
            "references": ["CIS Control 10"],
            "risk_level": "medium",
            "confidence": 0.75,
        },
        schema_name="ConsultantFinding",
    ) is True


@pytest.mark.unit
def test_consultant_finding_gaps_lists_missing_fields() -> None:
    gaps = consultant_finding_gaps({"summary": "only summary", "recommendations": ["one"]})
    assert "missing_topic" in gaps
    assert "missing_recommendations" in gaps
    assert "missing_confidence" in gaps


@pytest.mark.unit
def test_has_planned_tool_calls_detects_json_plan() -> None:
    assert has_planned_tool_calls({"tool_calls": [{"tool_name": "playbook_search"}]}) is True
    assert has_planned_tool_calls(
        {"tool_calls": [{"name": "load_skill", "arguments": {"skill_name": "veil-knowledge"}}]}
    ) is True
    assert has_planned_tool_calls({"topic": "x", "summary": "y"}) is False


@pytest.mark.unit
def test_preserve_planned_tool_calls_keeps_tool_list_after_validation_shape() -> None:
    from cys_core.application.workers.finding_quality import preserve_planned_tool_calls

    source = {"tool_calls": [{"name": "load_skill", "arguments": {"skill_name": "veil-knowledge"}}]}
    out = preserve_planned_tool_calls(source, {"topic": "", "summary": ""})
    assert out["tool_calls"] == source["tool_calls"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planned_tool_calls_without_execution_fails_job() -> None:
    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "tool_calls": [{"tool_name": "playbook_search", "tool_arguments": {}}],
            }
        )
    )
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="ConsultantFinding",
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
        get=lambda name: schema_registry.get("ConsultantFinding")
    )
    job = WorkerJob(
        job_id="consultant-evt-3-ccc",
        event_id="evt-3",
        persona="consultant",
        correlation_id="inv-3",
    )

    result = await runner.execute(job, job, "worker:consultant:consultant-evt-3-ccc", {})

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("tools_not_executed:")
    job_store.mark_failed.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planned_tool_calls_with_name_field_fails_as_tools_not_executed() -> None:
    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "tool_calls": [
                    {"name": "load_skill", "arguments": {"skill_name": "veil-knowledge"}},
                ],
            }
        )
    )
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="ConsultantFinding",
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
        get=lambda name: schema_registry.get("ConsultantFinding")
    )
    job = WorkerJob(
        job_id="consultant-evt-3b-ccc",
        event_id="evt-3b",
        persona="consultant",
        correlation_id="inv-3b",
    )

    result = await runner.execute(job, job, "worker:consultant:consultant-evt-3b-ccc", {})

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("tools_not_executed:")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_consultant_finding_fails_job() -> None:
    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "summary": "Deploy antivirus only",
                "recommendations": [],
                "confidence": 0,
            }
        )
    )
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="ConsultantFinding",
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
        get=lambda name: schema_registry.get("ConsultantFinding")
    )
    job = WorkerJob(
        job_id="consultant-evt-1-aaa",
        event_id="evt-1",
        persona="consultant",
        correlation_id="inv-1",
    )

    result = await runner.execute(job, job, "worker:consultant:consultant-evt-1-aaa", {})

    assert result.success is False
    job_store.mark_failed.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_valid_consultant_finding_completes_job() -> None:
    runtime = SimpleNamespace(
        arun=AsyncMock(
            return_value={
                "topic": "Malware defense",
                "summary": "Use EDR and patching",
                "recommendations": ["Deploy EDR", "Patch OS monthly"],
                "references": ["NIST CSF PR.DS"],
                "risk_level": "medium",
                "confidence": 0.8,
            }
        )
    )
    registry = SimpleNamespace(
        get=lambda _name: SimpleNamespace(
            schema_name="ConsultantFinding",
            tools=[],
            skills=[],
            bus_recipients=["critic", "coordinator"],
        )
    )
    job_store = MagicMock()
    runner = build_run_worker_job_for_tests(
        runtime=runtime,
        registry=registry,
        job_store=job_store,
    )
    runner._result_validator._schema_registry = SimpleNamespace(
        get=lambda name: schema_registry.get("ConsultantFinding")
    )
    job = WorkerJob(
        job_id="consultant-evt-2-bbb",
        event_id="evt-2",
        persona="consultant",
        correlation_id="inv-2",
    )

    result = await runner.execute(job, job, "worker:consultant:consultant-evt-2-bbb", {})

    assert result.success is True
    job_store.mark_completed.assert_called_once()
