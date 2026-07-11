from __future__ import annotations

import pytest

from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_merged_manifest,
    hydrate_job_from_snapshot,
    tool_succeeded,
)
from cys_core.domain.evidence.models import EvidenceManifest, Observation
from cys_core.domain.evidence.snapshot import EvidenceSnapshot


@pytest.mark.unit
def test_hydrate_job_from_snapshot_seeds_manifest() -> None:
    job_id = "soc-revision-1"
    clear_tool_execution_count(job_id)
    manifest = EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs-1",
                kind="process",
                value="cmd.exe",
                source_tool="siem",
                source_path="events",
            )
        ],
        telemetry_level="rich",
    )
    snapshot = EvidenceSnapshot(
        investigation_id="eng-1",
        tenant_id="default",
        persona_manifests={"soc": manifest},
        merged_manifest=manifest,
    )
    hydrate_job_from_snapshot(job_id, snapshot)
    assert tool_succeeded(job_id, "investigate_incident") is True
    merged = get_merged_manifest(job_id)
    assert merged is not None
    assert merged.observations[0].obs_id == "obs-1"
