from __future__ import annotations

from cys_core.application.workers.evidence_gate import soc_evidence_gaps
from cys_core.domain.evidence.manifest_builder import build_manifest_from_investigation
from cys_core.domain.evidence.models import EvidenceRef


def _inc893743_sparse_payload() -> dict:
    return {
      "incident_id": "382ae7ae-4cd1-4319-a3dc-287c88140a1a",
      "summary": {
          "key": "INC-893743",
          "correlation_rules": ["malicious_pipe_created", "kata_taa_high_alert"],
          "category": "MalwareDetection",
      },
      "incident": {
          "id": "382ae7ae-4cd1-4319-a3dc-287c88140a1a",
          "key": "INC-893743",
          "category": "MalwareDetection",
          "type": "HackToolsDetection",
          "correlationRuleNames": ["malicious_pipe_created", "kata_taa_high_alert"],
          "targets": [
              {"name": "ms-113.tpsgroup.ru", "addresses": ["192.168.15.112"]},
          ],
      },
      "linked_events": {"events": []},
      "recent_events": {"events": [], "truncated": False},
    }


def test_manifest_inc893743_sparse_kata():
    manifest = build_manifest_from_investigation(_inc893743_sparse_payload())
    assert manifest.telemetry_level == "sparse"
    assert manifest.max_confidence <= 0.5
    assert "kata_taa_console" in manifest.required_external_sources
    assert any(gap.field == "subject.process.cmdline" for gap in manifest.data_gaps)
    host_values = {obs.value for obs in manifest.observations if obs.kind == "host"}
    assert "ms-113.tpsgroup.ru" in host_values


def test_soc_gate_rejects_hallucinated_inc893743():
    manifest = build_manifest_from_investigation(_inc893743_sparse_payload())
    finding = {
        "summary": (
            "Credential Dumping on ms-113.tpsgroup.ru: svchost.exe PID 4 created "
            "\\\\.\\pipe\\lsass_pipe (Mimikatz). T1003.001."
        ),
        "confidence": 0.85,
        "mitre_techniques": ["T1003.001"],
        "telemetry_level": "sparse",
        "evidence": [],
        "data_gaps": [],
    }
    gaps = soc_evidence_gaps(finding, manifest)
    assert "missing_evidence_refs" in gaps
    assert "confidence_exceeds_manifest_cap" in gaps
    assert any(gap.startswith("ungrounded_entity:") for gap in gaps)


def test_soc_gate_passes_grounded_sparse_inc893743():
    manifest = build_manifest_from_investigation(_inc893743_sparse_payload())
    host_obs = next(obs for obs in manifest.observations if obs.kind == "host")
    rule_obs = next(obs for obs in manifest.observations if obs.kind == "correlation_rule")
    finding = {
        "summary": (
            "KATA TAA alert malicious_pipe_created on ms-113.tpsgroup.ru; "
            "process cmdline unavailable in SIEM."
        ),
        "confidence": 0.45,
        "telemetry_level": "sparse",
        "evidence": [
            EvidenceRef(obs_id=host_obs.obs_id, excerpt=host_obs.value).model_dump(),
            EvidenceRef(obs_id=rule_obs.obs_id, excerpt=rule_obs.value).model_dump(),
        ],
        "data_gaps": [gap.model_dump() for gap in manifest.data_gaps],
    }
    gaps = soc_evidence_gaps(finding, manifest)
    assert gaps == []


def _inc893775_phishing_payload() -> dict:
    return {
        "incident_id": "6eb0593f-77cb-4337-8f83-87b0cf438404",
        "summary": {
            "key": "INC-893775",
            "name": "KSMG_message_with_suspicious_url",
            "category": "Attack",
            "type": "Phishing",
            "correlation_rules": [],
        },
        "incident": {
            "id": "6eb0593f-77cb-4337-8f83-87b0cf438404",
            "key": "INC-893775",
            "name": "KSMG_message_with_suspicious_url",
            "category": "Attack",
            "type": "Phishing",
            "correlationRuleNames": [],
        },
        "linked_events": {"events": []},
        "recent_events": {
            "events": [
                {
                    "uuid": "1111dbf8-79f6-11f1-83d5-746fd0e90113",
                    "correlation_name": "KSMG_message_with_suspicious_url",
                }
            ],
            "truncated": False,
        },
    }


def test_soc_gate_accepts_truncated_obs_id_inc893775():
    manifest = build_manifest_from_investigation(_inc893775_phishing_payload())
    rule_obs = next(obs for obs in manifest.observations if obs.kind == "correlation_rule")
    truncated_obs_id = rule_obs.obs_id.replace("1111dbf8", "1dbf8", 1)
    finding = {
        "summary": (
            "Phishing alert KSMG_message_with_suspicious_url in email; "
            "suspicious URL detected, endpoint context unavailable in SIEM."
        ),
        "confidence": 0.45,
        "telemetry_level": "sparse",
        "evidence": [
            EvidenceRef(
                obs_id=truncated_obs_id,
                excerpt="KSMG_message_with_suspicious_url",
            ).model_dump(),
            EvidenceRef(obs_id="obs:incident_key:inc-893775", excerpt="INC-893775").model_dump(),
        ],
        "data_gaps": [gap.model_dump() for gap in manifest.data_gaps],
    }
    gaps = soc_evidence_gaps(finding, manifest)
    assert gaps == []
