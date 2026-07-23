from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePolicyPayload
from cys_core.domain.catalog.validation import CatalogValidationError, CrossRefValidator
from cys_core.domain.engagement.bus_routing import off_plan_bus_enqueue_reason
from cys_core.domain.engagement.models import Engagement, EngagementStatus, SynthesisStatus
from cys_core.domain.evidence.coercion import coerce_evidence_refs, coerce_sparse_soc_finding
from cys_core.domain.evidence.gaps import consultant_synthesis_gaps, soc_evidence_gaps
from cys_core.domain.evidence.manifest_builder import build_manifest_from_investigation
from cys_core.domain.evidence.models import EvidenceManifest, EvidenceRef, Observation
from cys_core.domain.evidence.resolver import entity_grounded, resolve_observation
from cys_core.domain.findings.quality_gates import finding_meets_minimum
from cys_core.domain.follow_up.models import is_follow_up_plan_iteration
from cys_core.domain.policy.pure import allow_tool_pure, mode_sets_from_policy
from cys_core.domain.runs.plan_models import EngagementPlannerOutput
from cys_core.domain.security.agent_bus import SecureAgentBus
from cys_core.domain.security.prompt_context import digest_matches
from cys_core.domain.security.sandbox_tokens import verify_sandbox_token
from cys_core.domain.security.system_prompt_assembler import (
    LANGUAGE_SUFFIX,
    assemble_trusted_system_context,
    resolve_persona_prompt,
    strip_language_suffix,
)
from cys_core.domain.tools.coercion import coerce_tool_args
from cys_core.domain.workers.failure_reason import classify_worker_failure
from cys_core.domain.workers.job_budget import JobBudgetTracker, configure_job_cost


@pytest.mark.unit
def test_soc_evidence_gaps_confidence_type_error() -> None:
    manifest = EvidenceManifest(telemetry_level="sparse", max_confidence=0.6)
    gaps = soc_evidence_gaps(
        {
            "summary": "seen",
            "confidence": object(),
            "telemetry_level": "sparse",
            "data_gaps": [{"field": "subject.process.cmdline", "reason": "not_in_siem"}],
            "evidence": [],
        },
        manifest,
    )
    assert "missing_evidence_refs" in gaps or gaps == []


@pytest.mark.unit
def test_consultant_synthesis_gaps_entity_backed_via_specialist_ref() -> None:
    manifest = EvidenceManifest(
        telemetry_level="sparse",
        max_confidence=0.6,
        observations=[
            Observation(
                obs_id="obs:text:pid",
                kind="event_text",
                value="parent pid 1234 spawned child",
                source_tool="siem",
                source_path="events",
            ),
        ],
    )
    gaps = consultant_synthesis_gaps(
        {"topic": "Wrap", "summary": "Suspicious pid 1234 activity", "confidence": 0.5},
        {"soc": manifest},
        specialist_findings=[
            {
                "finding": {
                    "evidence": [
                        {"obs_id": "obs:text:pid", "excerpt": "pid 1234"},
                    ],
                },
            },
        ],
    )
    assert gaps == []


@pytest.mark.unit
def test_manifest_builder_skips_blank_observation_value() -> None:
    manifest = build_manifest_from_investigation(
        {
            "incident": {},
            "linked_events": {
                "events": [{"uuid": "e1", "subject": {"process": {"cmdline": "   "}}}],
            },
        }
    )
    assert all("cmdline" not in obs.value for obs in manifest.observations)


@pytest.mark.unit
def test_resolve_observation_uuid_exact_and_entity_grounded_branches() -> None:
    manifest = EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs:evt:abc:process:malware.exe",
                kind="process",
                value="malware.exe",
                source_tool="siem",
                source_path="events",
                event_uuid="abc",
            ),
            Observation(
                obs_id="obs:pid:1234",
                kind="pid",
                value="1234",
                source_tool="siem",
                source_path="events",
            ),
            Observation(
                obs_id="obs:pipe:test",
                kind="pipe",
                value=r"\\.\pipe\test",
                source_tool="siem",
                source_path="events",
            ),
            Observation(
                obs_id="obs:account:domain_user",
                kind="account",
                value="DOMAIN\\user",
                source_tool="siem",
                source_path="events",
            ),
        ]
    )
    exact = resolve_observation(EvidenceRef(obs_id="obs:evt:abc:process:malware.exe"), manifest)
    assert exact is not None
    assert entity_grounded("process", "malware.exe", manifest) is True
    assert entity_grounded("pid", "1234", manifest) is True
    assert entity_grounded("pipe", "test", manifest) is True
    assert entity_grounded("account", "domain", manifest) is True
    missing = resolve_observation(
        EvidenceRef(obs_id="obs:evt:missing:process:nope", excerpt="nope"),
        EvidenceManifest(),
    )
    assert missing is None


@pytest.mark.unit
def test_coerce_evidence_refs_non_list_and_sparse_confidence_error() -> None:
    assert coerce_evidence_refs({"evidence": "not-list"}) == []
    manifest = EvidenceManifest(telemetry_level="sparse", max_confidence=0.5, data_gaps=[])
    finding = {"summary": "x", "confidence": object()}
    assert coerce_sparse_soc_finding(finding, manifest) is True


@pytest.mark.unit
def test_coerce_tool_args_non_string_scalar_paths() -> None:
    assert coerce_tool_args({"count": 7}) == {"count": 7}
    assert coerce_tool_args({"items": ["1", "2"]}) == {"items": [1, 2]}
    assert coerce_tool_args({"outer": {"flag": "false"}})["outer"]["flag"] is False
    assert coerce_tool_args({"list": [1, {"x": "1"}]})["list"][1]["x"] == 1


@pytest.mark.unit
def test_bus_routing_revision_on_plan_and_escalation_filter_empty() -> None:
    assert off_plan_bus_enqueue_reason("soc", ["soc"], msg_type="revision") is None
    assert off_plan_bus_enqueue_reason("intel", ["soc"], msg_type="finding") == "finding_off_plan"
    from cys_core.domain.engagement.bus_routing import filter_escalation_recipients

    assert filter_escalation_recipients("unknown", ["soc"], msg_type="finding") == ["soc"]


@pytest.mark.unit
def test_engagement_model_remaining_branches() -> None:
    engagement = Engagement(id="e1", goal="g", planner_plan=["soc"])
    assert engagement.specialists_terminal(plan_personas=[]) is False
    engagement = Engagement(
        id="e2",
        goal="g",
        status=EngagementStatus.RUNNING,
        planner_plan=["soc"],
        synthesis_persona="consultant",
        failed_personas=["soc"],
        completed_personas=[],
    )
    engagement.record_persona_completed("soc")
    assert "soc" not in engagement.failed_personas
    engagement = Engagement(
        id="e3",
        goal="g",
        status=EngagementStatus.RUNNING,
        planner_plan=["soc"],
        synthesis_persona="consultant",
        completed_personas=["soc"],
    )
    engagement.record_persona_failed("consultant")
    engagement = Engagement(id="e4", goal="g")
    engagement.apply_planner_result(["soc"], status="ready", synthesis_persona="consultant")
    assert engagement.synthesis_status == SynthesisStatus.PENDING


@pytest.mark.unit
def test_system_prompt_assembler_suffix_and_persona_paths() -> None:
    entry = SimpleNamespace(persona_prompt="You are SOC.", system_prompt="")
    assert resolve_persona_prompt(entry) == "You are SOC."
    ctx = assemble_trusted_system_context(f"You are SOC.{LANGUAGE_SUFFIX}", language="ru")
    assert LANGUAGE_SUFFIX in ctx.text
    assert strip_language_suffix(f"You are SOC.{LANGUAGE_SUFFIX}") == "You are SOC."


@pytest.mark.unit
def test_cross_ref_validator_blocks_policy_tools() -> None:
    policy = SimpleNamespace(tool_allowlist={"cybersec-soc": ["read_file"]})

    def getter(_profile_id: str):
        return policy

    validator = CrossRefValidator(known_tool_names={"read_file", "execute_command"}, policy_getter=getter)
    entry = AgentCatalogEntry(name="soc", profile_id="cybersec-soc", tools=["read_file", "execute_command"])
    with pytest.raises(CatalogValidationError, match="blocked by profile policy"):
        validator.validate_agent(entry)


@pytest.mark.unit
def test_policy_pure_default_mode_sets_and_mutating_prefix() -> None:
    assert mode_sets_from_policy(None)[0]
    assert allow_tool_pure(None, "search_events") is True


@pytest.mark.unit
def test_engagement_planner_output_non_dict_and_non_list_sub_goals() -> None:
    parsed = EngagementPlannerOutput.model_validate({"personas": ["soc"], "sub_goals": {"soc": "x"}})
    assert parsed.sub_goals == {"soc": "x"}
    coerced = EngagementPlannerOutput._coerce_sub_goals({"personas": ["soc"], "sub_goals": "not-a-list"})
    assert coerced["sub_goals"] == "not-a-list"
    assert EngagementPlannerOutput._coerce_sub_goals("not-a-dict") == "not-a-dict"


@pytest.mark.unit
def test_sandbox_token_malformed_payload() -> None:
    assert verify_sandbox_token("not-a-token", secret=b"key") is None


@pytest.mark.unit
def test_agent_bus_default_escalation_paths() -> None:
    bus = SecureAgentBus(signing_key=b"key", policy=ProfilePolicyPayload(escalation_paths=[]))
    assert bus._escalation_paths


@pytest.mark.unit
def test_digest_matches_exact_only() -> None:
    assert digest_matches("abc", "abc") is True
    assert digest_matches("abc", "def") is False


@pytest.mark.unit
def test_classify_worker_failure_sandbox_error_string() -> None:
    reason = classify_worker_failure(None, error_string="sandbox destroy failed")
    from cys_core.domain.workers.failure_reason import WorkerJobFailureReason

    assert reason == WorkerJobFailureReason.SANDBOX_ERROR


@pytest.mark.unit
def test_job_budget_profile_specific_rate() -> None:
    JobBudgetTracker.clear_all()
    configure_job_cost(0.02, profile_id="profile-x")
    JobBudgetTracker.configure("sess-x", max_tokens=5000, max_cost_usd=1.0, max_tool_calls=1, profile_id="profile-x")
    JobBudgetTracker.record_tokens("sess-x", 1000)
    JobBudgetTracker.clear_all()


@pytest.mark.unit
def test_follow_up_plan_iteration_requires_planning_kind() -> None:
    assert is_follow_up_plan_iteration({"work_kind": "investigation", "phase": "plan"}) is False


@pytest.mark.unit
def test_memory_list_by_tenant_filters_expired_and_bad_checksum() -> None:
    from cys_core.domain.memory.models import MemoryEntry, MemoryScope
    from cys_core.domain.memory.services import MemoryReadService
    from cys_core.domain.memory.validator import MemoryEntryValidator

    class TenantStore:
        def __init__(self) -> None:
            self._entries: list[MemoryEntry] = []

        def query(self, scope: MemoryScope, *, limit: int = 20) -> list[MemoryEntry]:
            return []

        def list_by_tenant(self, tenant_id: str, *, limit: int = 100, agent: str | None = None):
            return [entry for entry in self._entries if entry.scope.tenant_id == tenant_id][:limit]

    store = TenantStore()
    reader = MemoryReadService(store, signing_key=b"key")
    validator = MemoryEntryValidator(namespace_key="t1:inv-old", signing_key=b"key")
    store._entries.append(
        MemoryEntry(
            scope=MemoryScope(tenant_id="t1", investigation_id="inv-old"),
            content="expired",
            source_agent="soc",
            source_job_id="job-1",
            checksum=validator.checksum("expired"),
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
    )
    store._entries.append(
        MemoryEntry(
            scope=MemoryScope(tenant_id="t1", investigation_id="inv-bad"),
            content="bad",
            source_agent="soc",
            source_job_id="job-2",
            checksum="bad",
            created_at=datetime.now(timezone.utc),
        )
    )
    assert reader.list_by_tenant("t1") == []


@pytest.mark.unit
def test_evidence_manifest_observation_index() -> None:
    manifest = EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs:1",
                kind="host",
                value="host-a",
                source_tool="siem",
                source_path="events",
            )
        ]
    )
    assert manifest.observation_index()["obs:1"].value == "host-a"
    assert manifest.observation_values() == {"host-a"}
    assert EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs:2",
                kind="host",
                value="",
                source_tool="siem",
                source_path="events",
            )
        ]
    ).observation_values() == set()


@pytest.mark.unit
def test_remaining_small_domain_branches() -> None:
    from cys_core.domain.engagement.bus_routing import off_plan_bus_enqueue_reason
    from cys_core.domain.evidence.coercion import coerce_data_gaps
    from cys_core.domain.evidence.resolver import resolve_observation
    from cys_core.domain.findings.models import ConductorStepResult
    from cys_core.domain.findings.packs.cybersec_soc import SocFinding
    from cys_core.domain.policy.defaults import get_persona_budgets
    from cys_core.domain.policy.pure import allow_tool_pure
    from cys_core.domain.runs.models import InteractionMode
    from cys_core.domain.security.sandbox_tokens import verify_sandbox_token
    from cys_core.domain.security.system_prompt_assembler import (
        LANGUAGE_SUFFIX,
        assemble_trusted_system_context,
        strip_language_suffix,
    )
    from cys_core.domain.tools.coercion import coerce_tool_args, normalize_technique_id, normalize_ti_category

    assert off_plan_bus_enqueue_reason("soc", ["soc"], msg_type="finding") is None
    assert off_plan_bus_enqueue_reason("soc", ["soc"], msg_type="delegate") is None
    assert coerce_data_gaps({"data_gaps": "not-list"}) == []
    assert normalize_technique_id("   ") == ""
    assert normalize_technique_id("INVALID") == "INVALID"
    assert normalize_ti_category(7) == ""
    assert normalize_ti_category("   ") == ""
    assert coerce_tool_args({"x": "not-json["})["x"] == "not-json["
    finding = SocFinding.model_validate(
        {
            "summary": "ok",
            "evidence": None,
            "data_gaps": None,
        }
    )
    assert finding.evidence == []
    assert finding.data_gaps == []
    finding2 = SocFinding.model_validate(
        {
            "summary": "ok",
            "data_gaps": [{"field": "subject.process.cmdline", "reason": "not_in_siem"}],
        }
    )
    assert finding2.data_gaps[0].field == "subject.process.cmdline"
    assert ConductorStepResult.model_validate({"reasoning_steps": None, "remaining_steps": None}).reasoning_steps == []
    assert allow_tool_pure(InteractionMode.PLAN, "spawn_worker") is False
    assert get_persona_budgets()["soc"].max_tokens > 0
    assert verify_sandbox_token("bad.token", secret=b"key") is None
    assert strip_language_suffix(f"Body{LANGUAGE_SUFFIX}") == "Body"
    assert assemble_trusted_system_context(f"Body{LANGUAGE_SUFFIX}", language="ru").persona.endswith(LANGUAGE_SUFFIX)
    manifest = EvidenceManifest(
        observations=[
            Observation(
                obs_id="obs:evt:full-uuid-9999:pid:1",
                kind="pid",
                value="1",
                source_tool="siem",
                source_path="events",
                event_uuid="full-uuid-9999",
            )
        ]
    )
    assert (
        resolve_observation(
            EvidenceRef(obs_id="obs:evt:uuid-9999:pid:1", excerpt="1"),
            manifest,
        )
        is not None
    )
    sparse = EvidenceManifest(telemetry_level="sparse", max_confidence=0.5)
    result = {
        "topic": "Wrap",
        "summary": "No new hosts.",
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
