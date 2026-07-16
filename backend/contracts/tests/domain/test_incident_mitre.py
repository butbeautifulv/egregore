from __future__ import annotations

import pytest

from cys_core.domain.evidence.incident_mitre import infer_suggested_mitre_techniques
from cys_core.domain.evidence.manifest_builder import build_manifest_from_investigation


@pytest.mark.unit
def test_infer_network_scan_to_t1046() -> None:
    techniques = infer_suggested_mitre_techniques(
        incident_type="NetworkScan",
        incident_name="Port_Scan_from_one_source_to_different_destination_internal",
        correlation_rules=["port_scan_from_one_source_to_different_destination_internal"],
    )
    assert techniques == ["T1046"]


@pytest.mark.unit
def test_infer_unknown_type_returns_empty() -> None:
    assert infer_suggested_mitre_techniques(incident_type="Undefined", incident_name="foo") == []


@pytest.mark.unit
def test_manifest_includes_suggested_mitre_for_inc893812_shape() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident_id": "b98081be-93ad-48f0-9f1d-083df73c3577",
            "incident": {
                "id": "b98081be-93ad-48f0-9f1d-083df73c3577",
                "key": "INC-893812",
                "name": "Port_Scan_from_one_source_to_different_destination_internal",
                "type": "NetworkScan",
                "category": "Attack",
                "correlationRuleNames": ["port_scan_from_one_source_to_different_destination_internal"],
            },
            "linked_events": {"events": []},
            "recent_events": {"events": [], "truncated": False},
        }
    )
    assert manifest.suggested_mitre_techniques == ["T1046"]
