from __future__ import annotations

import pytest

from cys_core.domain.engagement.bus_routing import off_plan_bus_enqueue_reason
from cys_core.domain.evidence.gaps import consultant_synthesis_gaps
from cys_core.domain.evidence.manifest_builder import _add_observation, build_manifest_from_investigation
from cys_core.domain.evidence.models import EvidenceManifest, EvidenceRef, Observation
from cys_core.domain.evidence.resolver import entity_grounded, resolve_observation
from cys_core.domain.findings.quality_gates import finding_meets_minimum
from cys_core.domain.parsing.json_text import _literal, _strip_prefixes, parse_loose_structured_text
from cys_core.domain.policy import defaults as policy_defaults
from cys_core.domain.policy.pure import _is_mutating, allow_tool_pure
from cys_core.domain.runs.models import InteractionMode
from cys_core.domain.security.sandbox_tokens import verify_sandbox_token
from cys_core.domain.security.system_prompt_assembler import (
    LANGUAGE_SUFFIX,
    assemble_trusted_system_context,
    strip_language_suffix,
)


@pytest.mark.unit
def test_off_plan_bus_enqueue_reason_finding_branch() -> None:
    assert off_plan_bus_enqueue_reason("hunter", ["soc"], msg_type="finding") == "finding_off_plan"


@pytest.mark.unit
def test_consultant_synthesis_skips_grounded_entities() -> None:
    manifest = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        observations=[
            Observation(
                obs_id="obs:process:cmd.exe",
                kind="process",
                value="cmd.exe",
                source_tool="siem",
                source_path="events",
            )
        ],
    )
    gaps = consultant_synthesis_gaps(
        {"topic": "Wrap", "summary": "cmd.exe executed", "confidence": 0.5},
        {"soc": manifest},
        specialist_findings=[],
    )
    assert gaps == []


@pytest.mark.unit
def test_off_plan_bus_enqueue_reason_delegate_off_plan() -> None:
    assert off_plan_bus_enqueue_reason("intel", ["soc"], msg_type="delegate") == "finding_off_plan"


@pytest.mark.unit
def test_off_plan_bus_enqueue_reason_unknown_msg_type() -> None:
    assert off_plan_bus_enqueue_reason("hunter", ["soc"], msg_type="heartbeat") is None


@pytest.mark.unit
def test_off_plan_bus_enqueue_reason_unknown_message_type() -> None:
    assert off_plan_bus_enqueue_reason("intel", ["soc"], msg_type="report") is None


@pytest.mark.unit
def test_manifest_builder_skips_blank_correlation_name() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {},
            "linked_events": {"events": [{"uuid": "e1", "correlation_name": "   "}]},
        }
    )
    assert all(obs.kind != "correlation_rule" for obs in manifest.observations)


@pytest.mark.unit
def test_allow_tool_pure_mutating_in_set() -> None:
    from cys_core.domain.catalog.models import ModePolicyPayload

    policy = ModePolicyPayload(mutating_tools=["custom_mutate"], plan_blocked_tools=["spawn_worker"])
    assert allow_tool_pure(InteractionMode.PLAN, "custom_mutate", mode_policy=policy) is False


@pytest.mark.unit
def test_parse_loose_structured_text_non_list_personas() -> None:
    assert parse_loose_structured_text("xxxxxxxxxxxxxxxxxxxx personas=('soc',)") is None


@pytest.mark.unit
def test_manifest_builder_blank_process_name_skipped() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {},
            "linked_events": {"events": [{"uuid": "e1", "subject": {"process": {"name": "   "}}}]},
        }
    )
    assert all(obs.value.strip() for obs in manifest.observations)


@pytest.mark.unit
def test_add_observation_skips_blank_value() -> None:
    observations: dict[str, Observation] = {}
    _add_observation(
        observations,
        kind="pid",
        value="   ",
        source_tool="siem",
        source_path="events",
    )
    assert observations == {}


@pytest.mark.unit
def test_resolve_observation_uuid_branches() -> None:
    manifest = EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs:evt:abcdef12:pid:9",
                kind="pid",
                value="9",
                source_tool="siem",
                source_path="events",
                event_uuid="abcdef12",
            )
        ]
    )
    assert resolve_observation(EvidenceRef(obs_id="obs:evt:missing:pid:9"), manifest) is None
    assert (
        resolve_observation(
            EvidenceRef(obs_id="obs:evt:cdef12:pid:9", excerpt="9"),
            manifest,
        )
        is not None
    )


@pytest.mark.unit
def test_resolve_uuid_fragment_no_actual_uuid() -> None:
    from cys_core.domain.evidence.resolver import _uuid_fragment_matches

    assert _uuid_fragment_matches("abcdef12", None) is False
    assert _uuid_fragment_matches("abcdef12", "abcdef12") is True
    assert _uuid_fragment_matches("abcdef12", "full-uuid-abcdef12") is True


@pytest.mark.unit
def test_parse_loose_json_direct_and_after_prefix() -> None:
    assert parse_loose_structured_text('{"personas": ["soc"]}') == {"personas": ["soc"]}
    assert (
        parse_loose_structured_text("Returning structured response: {\"personas\": [\"soc\"]}")
        == {"personas": ["soc"]}
    )
    assert parse_loose_structured_text("xxxxxxxxxxxxxxxxxxxx personas=(123)") is None
    assert parse_loose_structured_text("personas=[1;2]") is None


@pytest.mark.unit
def test_finding_meets_minimum_consultant_non_synthesis() -> None:
    result = {
        "topic": "Advisory",
        "summary": "Guidance",
        "recommendations": ["A", "B"],
        "confidence": 0.8,
    }
    assert finding_meets_minimum("consultant", result, schema_name="ConsultantFinding") is True


@pytest.mark.unit
def test_allow_tool_pure_named_mutating_tool() -> None:
    from cys_core.domain.policy.defaults import MUTATING_TOOLS

    tool = next(iter(MUTATING_TOOLS))
    assert allow_tool_pure(InteractionMode.PLAN, tool) is False


@pytest.mark.unit
def test_is_mutating_exact_set_member() -> None:
    assert _is_mutating("custom_mutate", frozenset({"custom_mutate"})) is True


@pytest.mark.unit
def test_system_prompt_apply_language_suffix_idempotent() -> None:
    from cys_core.domain.security.system_prompt_assembler import _apply_language_suffix

    body = f"You are SOC.{LANGUAGE_SUFFIX}"
    assert _apply_language_suffix(body, language="ru") == body


@pytest.mark.unit
def test_parse_loose_structured_text_literal_and_prefix_paths() -> None:
    assert _literal("not-valid") is None
    assert _strip_prefixes("Returning structured response: personas=['soc']") == "personas=['soc']"
    parsed = parse_loose_structured_text(
        "Returning structured response: personas=['soc'] sub_goals={} rationale='x' "
        "execution_mode='parallel' synthesis_persona='consultant'"
    )
    assert parsed is not None
    assert parsed["personas"] == ["soc"]
    assert parsed["execution_mode"] == "parallel"
    assert parsed["synthesis_persona"] == "consultant"


@pytest.mark.unit
def test_sandbox_token_invalid_payload() -> None:
    import base64
    import hashlib
    import hmac
    import json
    import time

    payload = {"exp": time.time() + 100}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(hmac.new(b"key", body.encode("ascii"), hashlib.sha256).digest()).rstrip(
        b"="
    ).decode()
    assert verify_sandbox_token(f"{body}.{signature}", secret=b"key") is None


@pytest.mark.unit
def test_system_prompt_suffix_idempotent() -> None:
    body = f"You are SOC.{LANGUAGE_SUFFIX}"
    assert assemble_trusted_system_context(body, language="ru").persona.count(LANGUAGE_SUFFIX) == 1
    assert strip_language_suffix("plain prompt") == "plain prompt"


@pytest.mark.unit
def test_get_persona_budgets_default_branch() -> None:
    policy_defaults._loaded_persona_budgets = None
    budgets = policy_defaults.get_persona_budgets()
    assert "soc" in budgets


@pytest.mark.unit
def test_finding_meets_minimum_consultant_sparse_synthesis() -> None:
    sparse = EvidenceManifest(telemetry_level="sparse", max_confidence=0.5)
    result = {
        "topic": "Wrap",
        "summary": "No new entities.",
        "recommendations": ["A", "B"],
        "confidence": 0.4,
    }
    assert (
        finding_meets_minimum(
            "consultant",
            result,
            schema_name="ConsultantFinding",
            upstream_manifests={"soc": sparse},
            phase="synthesis",
            specialist_findings=[],
        )
        is True
    )
