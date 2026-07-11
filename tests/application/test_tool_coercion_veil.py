from __future__ import annotations

import pytest
import structlog

from cys_core.application.runs.tool_coercion import (
    normalize_technique_id,
    normalize_veil_tool_args,
    prepare_veil_tool_invocation,
    veil_playbook_id_hint,
    veil_technique_id_hint,
    veil_ti_category_hint,
)
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    record_evidence_manifest,
)
from cys_core.domain.evidence.models import EvidenceManifest


@pytest.mark.unit
def test_normalize_veil_playbook_procedure_skill_id() -> None:
    args = normalize_veil_tool_args("playbook_procedure", {"skill_id": "skill-abc"})
    assert args["id"] == "skill-abc"


@pytest.mark.unit
def test_normalize_veil_nested_kwargs() -> None:
    args = normalize_veil_tool_args(
        "playbook_get",
        {"kwargs": {"playbook_id": "pb-1"}},
    )
    assert args["id"] == "pb-1"


@pytest.mark.unit
def test_normalize_veil_ti_query_and_category_aliases() -> None:
    args = normalize_veil_tool_args("ti_search_in_category", {"q": "10.0.0.1", "cat": "ioc"})
    assert args["query"] == "10.0.0.1"
    assert args["category"] == "ti"


@pytest.mark.unit
def test_prepare_veil_ti_search_rejects_empty_query() -> None:
    result = prepare_veil_tool_invocation("ti_search_in_category", {"category": "ti"})
    assert result["success"] is False
    assert result["reason"] == "invalid_args"
    assert "query is required" in result["error"]


@pytest.mark.unit
def test_prepare_veil_ti_search_rejects_unknown_category() -> None:
    result = prepare_veil_tool_invocation("ti_search_in_category", {"category": "not-a-real-cat", "query": "x"})
    assert result["success"] is False
    assert result["reason"] == "invalid_args"
    assert "unknown category" in result["error"]


@pytest.mark.unit
def test_prepare_veil_playbook_get_rejects_missing_id() -> None:
    result = prepare_veil_tool_invocation("playbook_get", {})
    assert result["success"] is False
    assert result["reason"] == "invalid_args"


@pytest.mark.unit
def test_prepare_veil_playbook_get_rejects_invalid_slug() -> None:
    result = prepare_veil_tool_invocation("playbook_get", {"id": "Bad_Slug"})
    assert result["success"] is False
    assert "slug" in result["error"]


@pytest.mark.unit
def test_normalize_technique_id_adds_prefix() -> None:
    assert normalize_technique_id("1059.001") == "T1059.001"
    assert normalize_technique_id("t1046") == "T1046"


@pytest.mark.unit
def test_prepare_veil_technique_normalizes_numeric_id() -> None:
    result = prepare_veil_tool_invocation("playbook_for_technique", {"technique_id": "1059.001"})
    assert result["arguments"]["technique_id"] == "T1059.001"


@pytest.mark.unit
def test_veil_playbook_id_hint() -> None:
    hint = veil_playbook_id_hint("playbook_procedure", "id is required")
    assert "playbook_search" in hint


@pytest.mark.unit
def test_normalize_veil_ti_category_ioc_alias() -> None:
    args = normalize_veil_tool_args(
        "ti_search_in_category",
        {"category": "ioc", "query": "10.0.0.1"},
    )
    assert args["category"] == "ti"


@pytest.mark.unit
def test_normalize_veil_ti_category_defaults_with_query() -> None:
    args = normalize_veil_tool_args("ti_search_in_category", {"query": "T1110"})
    assert args["category"] == "ti"


@pytest.mark.unit
def test_veil_ti_category_hint() -> None:
    hint = veil_ti_category_hint("ti_search_in_category", "unknown category: ioc")
    assert "category: ti" in hint or "use ti" in hint


@pytest.mark.unit
def test_normalize_playbook_for_technique_aliases() -> None:
    args = normalize_veil_tool_args("playbook_for_technique", {"mitre_technique": "T1046"})
    assert args["technique_id"] == "T1046"


@pytest.mark.unit
def test_normalize_playbook_for_technique_autofill_from_manifest() -> None:
    job_id = "job-technique-autofill"
    clear_tool_execution_count(job_id)
    structlog.contextvars.bind_contextvars(job_id=job_id)
    record_evidence_manifest(
        job_id,
        "investigate_incident",
        EvidenceManifest(telemetry_level="sparse", suggested_mitre_techniques=["T1046"]),
    )
    args = normalize_veil_tool_args("playbook_for_technique", {})
    assert args["technique_id"] == "T1046"
    clear_tool_execution_count(job_id)


@pytest.mark.unit
def test_veil_technique_id_hint() -> None:
    hint = veil_technique_id_hint("playbook_for_technique", "technique_id is required")
    assert "playbook_search" in hint
    assert "T1046" in hint
