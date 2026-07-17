from __future__ import annotations

import pytest

from cys_core.domain.evidence.models import EvidenceManifest
from cys_core.domain.evidence.snapshot import EvidenceSnapshot
from cys_core.domain.work_order.intake import WorkOrderIntake


@pytest.mark.unit
def test_evidence_snapshot_primary_manifest_prefers_merged() -> None:
    merged = EvidenceManifest(telemetry_level="rich")
    persona = EvidenceManifest(telemetry_level="sparse")
    snapshot = EvidenceSnapshot(
        investigation_id="inv-1",
        persona_manifests={"soc": persona},
        merged_manifest=merged,
    )
    assert snapshot.primary_manifest() is merged


@pytest.mark.unit
def test_evidence_snapshot_primary_manifest_falls_back_to_first_persona() -> None:
    persona = EvidenceManifest(telemetry_level="sparse")
    snapshot = EvidenceSnapshot(investigation_id="inv-1", persona_manifests={"soc": persona})
    assert snapshot.primary_manifest() is persona


@pytest.mark.unit
def test_evidence_snapshot_primary_manifest_empty_returns_none() -> None:
    snapshot = EvidenceSnapshot(investigation_id="inv-1")
    assert snapshot.primary_manifest() is None


@pytest.mark.unit
def test_work_order_intake_coerces_scalar_lists() -> None:
    intake = WorkOrderIntake(goal=" Investigate ", alert_ids="alert-1", iocs=[" 1.2.3.4 ", ""])
    assert intake.normalized_goal() == "Investigate"
    assert intake.alert_ids == ["alert-1"]
    assert intake.iocs == ["1.2.3.4"]


@pytest.mark.unit
def test_work_order_intake_coerces_none_lists_to_empty() -> None:
    intake = WorkOrderIntake(alert_ids=None, log_refs=None)
    assert intake.alert_ids == []
    assert intake.log_refs == []
