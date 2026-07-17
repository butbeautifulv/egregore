from __future__ import annotations

import pytest

from cys_core.domain.evidence.models import EvidenceManifest
from cys_core.domain.evidence.snapshot import EvidenceSnapshot
from cys_core.domain.workers.continuation import JobContinuation, JobContinuationKind


@pytest.mark.unit
def test_job_continuation_kind_values() -> None:
    assert JobContinuationKind.REVISION == "revision"
    assert JobContinuationKind.FOLLOW_UP_CHILD == "follow_up_child"


@pytest.mark.unit
def test_job_continuation_defaults_and_snapshot() -> None:
    manifest = EvidenceManifest(telemetry_level="sparse")
    snapshot = EvidenceSnapshot(investigation_id="inv-1", persona_manifests={"soc": manifest})
    continuation = JobContinuation(
        work_kind=JobContinuationKind.REVISION,
        snapshot=snapshot,
        parent_job_id="job-parent",
        notes="retry after critic",
    )
    assert continuation.work_kind is JobContinuationKind.REVISION
    assert continuation.snapshot is not None
    assert continuation.snapshot.investigation_id == "inv-1"
    assert continuation.parent_job_id == "job-parent"
    assert continuation.notes == "retry after critic"
