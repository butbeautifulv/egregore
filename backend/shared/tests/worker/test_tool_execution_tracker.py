from __future__ import annotations

import json

import pytest

from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_merged_manifest,
    ingest_tool_output_manifest,
    record_tool_success,
    tool_succeeded,
)


@pytest.mark.unit
def test_tool_succeeded_tracks_per_job() -> None:
    clear_tool_execution_count("job-1")
    assert tool_succeeded("job-1", "investigate_incident") is False
    record_tool_success("job-1", "investigate_incident")
    assert tool_succeeded("job-1", "investigate_incident") is True
    clear_tool_execution_count("job-1")
    assert tool_succeeded("job-1", "investigate_incident") is False


@pytest.mark.unit
def test_ingest_investigate_incident_merges_suggested_mitre() -> None:
    job_id = "job-ingest-mitre"
    clear_tool_execution_count(job_id)
    preview = json.dumps(
        {
            "success": True,
            "content": {
                "incident_id": "b98081be-93ad-48f0-9f1d-083df73c3577",
                "incident": {
                    "id": "b98081be-93ad-48f0-9f1d-083df73c3577",
                    "key": "INC-893812",
                    "name": "Port_Scan_from_one_source_to_different_destination_internal",
                    "type": "NetworkScan",
                },
                "linked_events": {"events": []},
                "recent_events": {"events": [], "truncated": False},
                "evidence_manifest": {
                    "telemetry_level": "sparse",
                    "max_confidence": 0.5,
                    "observations": [],
                    "availability": {},
                    "data_gaps": [],
                    "suggested_mitre_techniques": [],
                },
            },
        }
    )
    manifest = ingest_tool_output_manifest(job_id, "investigate_incident", preview)
    assert manifest is not None
    merged = get_merged_manifest(job_id)
    assert merged is not None
    assert merged.suggested_mitre_techniques == ["T1046"]
    clear_tool_execution_count(job_id)
