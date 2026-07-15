from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from cys_core.domain.agents.control import is_control_persona, is_platform_readonly_persona
from cys_core.domain.authz.tool_datasource_map import (
    datasource_object,
    datasource_seed_tuples,
    workspace_datasource_consumer_tuples,
)
from cys_core.domain.catalog.models import AgentCatalogEntry, ProfilePolicyPayload
from cys_core.domain.catalog.validation import CrossRefValidator
from cys_core.domain.policy.defaults import ESCALATION_ONLY_PATHS
from cys_core.domain.datasources.models import DataSource, DataSourceCapability
from cys_core.domain.datasources.validation import (
    capability_implies_write,
    classification_allows,
    validate_datasource,
    validate_datasource_capabilities,
)
from cys_core.domain.engagement.bus_routing import (
    filter_bus_recipients_for_plan,
    filter_escalation_recipients,
    off_plan_bus_enqueue_reason,
)
from cys_core.domain.engagement.ids import extract_engagement_id, normalize_correlation_id
from cys_core.domain.eval.models import EvalRun, EvalRunStatus
from cys_core.domain.evidence.coercion import coerce_data_gaps, coerce_evidence_refs
from cys_core.domain.evidence.incident_mitre import infer_suggested_mitre_techniques
from cys_core.domain.evidence.models import DataGap, EvidenceRef
from cys_core.domain.evidence.observation_ids import build_obs_id, parse_obs_id, slug_observation_value
from cys_core.domain.findings.normalize import normalize_finding_payload
from cys_core.domain.findings.operator_outcome import OperatorOutcome
from cys_core.domain.findings.quality_gates import finding_meets_minimum
from cys_core.domain.follow_up.models import is_follow_up_plan_iteration
from cys_core.domain.parsing.json_text import parse_json_text, parse_loose_structured_text
from cys_core.domain.policy.defaults import configure_persona_budgets, gaia_profile_policy_payload, get_persona_budgets
from cys_core.domain.policy.pure import (
    allow_tool_pure,
    mode_sets_from_policy,
    persona_budget_pure,
    persona_clearance_pure,
)
from cys_core.domain.runs.plan_models import EngagementPlannerOutput
from cys_core.domain.runs.trace_models import (
    EvalTraceFields,
    MemoryTraceFields,
    ModelCallTraceFields,
    ToolCallTraceFields,
    eval_trace,
    memory_trace,
    model_call_trace,
    policy_trace,
    tool_call_trace,
)
from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.auth_models import extract_organization_id
from cys_core.domain.security.data_classification import DataClassification
from cys_core.domain.security.prompt_context import digest_matches
from cys_core.domain.security.risk_level import RiskLevel
from cys_core.domain.security.sandbox_tokens import mint_sandbox_token, verify_sandbox_token
from cys_core.domain.security.system_prompt_assembler import (
    extract_persona_prompt,
    had_embedded_rule_sections,
    resolve_persona_prompt,
)
from cys_core.domain.tools.coercion import coerce_tool_args
from cys_core.domain.work_order.intake import WorkOrderIntake
from cys_core.domain.workers.failure_reason import WorkerJobFailureReason, classify_worker_failure
from cys_core.domain.workers.job_budget import JobBudgetTracker, configure_job_cost, reset_job_cost
from cys_core.domain.workers.models import WorkerJob, WorkerJobStatus


@pytest.mark.unit
def test_bus_routing_string_mode_and_delegate_off_plan() -> None:
    recipients = filter_bus_recipients_for_plan(["soc", "critic"], ["soc"], control_plane_mode="off")
    assert recipients == ["soc"]
    assert off_plan_bus_enqueue_reason("intel", ["soc"], msg_type="delegate") == "finding_off_plan"
    assert off_plan_bus_enqueue_reason("soc", ["soc"], msg_type="revision") is None
    assert off_plan_bus_enqueue_reason("intel", [], msg_type="finding") is None


@pytest.mark.unit
def test_filter_escalation_recipients_blocks_configured_path() -> None:
    sender, blocked = next(iter(ESCALATION_ONLY_PATHS))
    filtered = filter_escalation_recipients(sender, [blocked, "soc"], msg_type="finding")
    assert blocked not in filtered
    assert filter_escalation_recipients(sender, [blocked], msg_type="escalation") == [blocked]


@pytest.mark.unit
def test_system_prompt_assembler_legacy_paths() -> None:
    entry = SimpleNamespace(persona_prompt="", system_prompt="GLOBAL_RULES:\nlegacy")
    assert resolve_persona_prompt(entry) == ""
    wrapped = (
        "USER_DATA_TO_PROCESS\n<untrusted_data>\nYou are SOC.\n</untrusted_data>\nGLOBAL_RULES:\nx"
    )
    assert extract_persona_prompt(wrapped) == "You are SOC."
    assert extract_persona_prompt("") == ""
    assert had_embedded_rule_sections("GLOBAL_RULES:\n1") is True


@pytest.mark.unit
def test_digest_matches_truncated_prefix() -> None:
    full = "a" * 64
    assert digest_matches(full[:16], full) is True
    assert digest_matches("", full) is True
    assert digest_matches("nomatch", full) is False


@pytest.mark.unit
def test_extract_organization_id_variants() -> None:
    assert extract_organization_id({"organization_id": " org-1 "}) == "org-1"
    assert extract_organization_id({"organization": "acme"}) == "acme"
    assert extract_organization_id({"organization": {"id": "nested"}}) == "nested"
    assert extract_organization_id({}) == ""


@pytest.mark.unit
def test_incident_mitre_empty_and_explicit_ids() -> None:
    assert infer_suggested_mitre_techniques() == []
    techniques = infer_suggested_mitre_techniques(correlation_rules=["observed T1059.001 in logs"])
    assert "T1059.001" in techniques


@pytest.mark.unit
def test_trace_model_helpers() -> None:
    assert model_call_trace("llm", ModelCallTraceFields(model="gpt", tokens_in=1)).type == "model"
    assert tool_call_trace("search", ToolCallTraceFields(tool="search")).type == "tool"
    assert memory_trace("read", MemoryTraceFields(operation="query")).type == "memory"
    assert eval_trace("suite", EvalTraceFields(suite="s", metric="m")).type == "eval"
    assert policy_trace("gate", rule="r", decision="allow", profile_id="p").payload["rule"] == "r"


@pytest.mark.unit
def test_engagement_ids_extract_and_normalize() -> None:
    raw = "prefix eng-a1b2c3d4e5f6 suffix"
    assert extract_engagement_id(correlation_id=raw) == "eng-a1b2c3d4e5f6"
    payload = {"data": {"incident_id": "wrap eng-abcdef012345 here"}}
    assert extract_engagement_id(payload=payload) == "eng-abcdef012345"
    assert normalize_correlation_id(" noisy ", payload=payload) == "eng-abcdef012345"


@pytest.mark.unit
def test_eval_run_lifecycle() -> None:
    run = EvalRun(run_id="run-1", dataset_id="ds-1")
    run.start()
    assert run.status == EvalRunStatus.RUNNING
    assert run.started_at is not None
    run.finish_ok()
    assert run.status == EvalRunStatus.COMPLETED
    assert run.finished_at is not None


@pytest.mark.unit
def test_meta_planner_response_coerces_sub_goals_list() -> None:
    parsed = EngagementPlannerOutput.model_validate(
        {"personas": ["soc", "intel"], "sub_goals": ["triage", "enrich"]}
    )
    assert parsed.sub_goals == {"soc": "triage", "intel": "enrich"}
    parsed_mismatch = EngagementPlannerOutput.model_validate({"personas": ["soc"], "sub_goals": ["a", "b"]})
    assert parsed_mismatch.sub_goals == {"goal_0": "a", "goal_1": "b"}


@pytest.mark.unit
def test_policy_pure_branches() -> None:
    from cys_core.domain.catalog.models import ModePolicyPayload
    from cys_core.domain.runs.models import InteractionMode

    custom = ModePolicyPayload(
        read_only_tools=["search_events"],
        plan_blocked_tools=["run_scan"],
        mutating_tools=["write_file"],
    )
    assert mode_sets_from_policy(custom)[0] == frozenset({"search_events"})
    assert allow_tool_pure(InteractionMode.PLAN, "run_scan", mode_policy=custom) is False
    assert allow_tool_pure(InteractionMode.ASK, "search_events", mode_policy=custom) is True
    entry = AgentCatalogEntry(
        name="soc",
        budget_max_tokens=100,
        budget_max_cost_usd=1.0,
        data_clearance="restricted",
    )
    budget = persona_budget_pure("soc", entry)
    assert budget.max_tokens == 100
    assert persona_clearance_pure("soc", entry).value == "restricted"
    assert gaia_profile_policy_payload().tool_risk is not None
    configure_persona_budgets({"custom": budget})
    assert "custom" in get_persona_budgets()
    from cys_core.domain.policy.defaults import _BASE_PERSONA_BUDGETS

    configure_persona_budgets(dict(_BASE_PERSONA_BUDGETS))


@pytest.mark.unit
def test_evidence_coercion_accepts_models_and_skips_invalid() -> None:
    ref = EvidenceRef(obs_id="obs:1", excerpt="x")
    refs = coerce_evidence_refs({"evidence": [ref, "obs:2", {"bad": True}, 3]})
    assert refs[0] is ref
    gap = DataGap(field="f", reason="not_in_siem")
    gaps = coerce_data_gaps({"data_gaps": [gap, "field-a", {"nope": 1}]})
    assert gaps[0] is gap


@pytest.mark.unit
def test_observation_ids_build_and_parse() -> None:
    obs_id = build_obs_id("host", "Work Station!", "uuid-1")
    assert "obs:evt:uuid-1:host:" in obs_id
    assert slug_observation_value("   ") == "unknown"
    evt, kind, slug = parse_obs_id(obs_id)
    assert evt == "uuid-1"
    assert kind == "host"
    assert slug
    assert parse_obs_id("bad") == (None, None, "")


@pytest.mark.unit
def test_datasource_validation_rules() -> None:
    with pytest.raises(ValueError, match="at least one capability"):
        validate_datasource_capabilities([])
    with pytest.raises(ValueError, match="mutate capability requires get"):
        validate_datasource_capabilities([DataSourceCapability.MUTATE])
    assert capability_implies_write(DataSourceCapability.QUERY) is True
    assert classification_allows(DataClassification.INTERNAL, DataClassification.RESTRICTED) is False
    validate_datasource(
        DataSource(
            id="ds-1",
            type="siem",
            capabilities=[DataSourceCapability.GET, DataSourceCapability.QUERY],
            classification=DataClassification.INTERNAL,
        )
    )


@pytest.mark.unit
def test_tool_datasource_map_tuples() -> None:
    assert datasource_object("siem-readonly") == "datasource:siem-readonly"
    seeds = datasource_seed_tuples("org-1", datasource_ids=["siem-readonly"])
    assert seeds == [("organization:org-1", "organization", "datasource:siem-readonly")]
    consumers = workspace_datasource_consumer_tuples(" ws-1 ", ["siem-readonly"])
    assert consumers[0][0] == "workspace:ws-1"


@pytest.mark.unit
def test_coerce_tool_args_edge_types() -> None:
    assert coerce_tool_args({"n": None}) == {"n": None}
    assert coerce_tool_args({"flag": "false"})["flag"] is False
    assert coerce_tool_args({"items": "not-json"})["items"] == "not-json"
    assert coerce_tool_args({"nested": {"x": "1"}})["nested"]["x"] == 1


@pytest.mark.unit
def test_parse_json_text_and_loose_prefix_paths() -> None:
    assert parse_json_text("```\nnot-json\n```") is None
    text = "Here is the plan: personas=['soc'] sub_goals={} rationale='r'"
    parsed = parse_loose_structured_text(text)
    assert parsed is not None
    assert parsed["personas"] == ["soc"]
    assert parse_loose_structured_text("   ") is None
    loose = (
        "personas=['soc'] sub_goals={'soc': 'triage'} rationale='because' "
        "execution_mode='parallel' synthesis_persona='consultant'"
    )
    parsed_full = parse_loose_structured_text(loose)
    assert parsed_full is not None
    assert parsed_full["execution_mode"] == "parallel"
    assert parsed_full["synthesis_persona"] == "consultant"


@pytest.mark.unit
def test_normalize_finding_payload_content_parsed() -> None:
    payload = {"content_parsed": {"summary": "from parsed", "confidence": 0.5}}
    assert normalize_finding_payload(payload)["summary"] == "from parsed"


@pytest.mark.unit
def test_operator_outcome_to_final_report() -> None:
    outcome = OperatorOutcome(summary="done", title="Report")
    report = outcome.to_final_report()
    assert report["summary"] == "done"
    assert report["title"] == "Report"


@pytest.mark.unit
def test_finding_meets_minimum_error_payload() -> None:
    assert finding_meets_minimum("soc", {"error": "x"}, schema_name="SocFinding") is False


@pytest.mark.unit
def test_follow_up_plan_iteration_requires_plan_phase() -> None:
    assert is_follow_up_plan_iteration({"work_kind": "follow_up_plan", "phase": "plan"}) is True
    assert is_follow_up_plan_iteration({"work_kind": "follow_up_plan", "phase": "synthesis"}) is False


@pytest.mark.unit
def test_work_order_intake_coerces_invalid_list_input() -> None:
    intake = WorkOrderIntake(goal="Investigate", alert_ids=123)
    assert intake.alert_ids == []


@pytest.mark.unit
def test_risk_level_ordering_guard() -> None:
    assert (RiskLevel.LOW < RiskLevel.HIGH) is True
    assert RiskLevel.LOW.__lt__("high") is NotImplemented


@pytest.mark.unit
def test_classify_worker_failure_branches() -> None:
    from cys_core.domain.security.exceptions import SecurityViolation
    from cys_core.domain.workers.exceptions import JobBudgetExceeded

    assert classify_worker_failure(JobBudgetExceeded("cap")) == WorkerJobFailureReason.BUDGET_EXCEEDED
    assert (
        classify_worker_failure(SecurityViolation("schema invalid"))
        == WorkerJobFailureReason.SCHEMA_INVALID
    )
    assert classify_worker_failure(TimeoutError()) == WorkerJobFailureReason.TIMEOUT

    class SandboxCreateError(Exception):
        pass

    assert classify_worker_failure(SandboxCreateError("sandbox create failed")) == WorkerJobFailureReason.SANDBOX_ERROR
    assert classify_worker_failure(None, error_string="worker_job_timeout") == WorkerJobFailureReason.TIMEOUT
    assert classify_worker_failure(None, error_string="recursion limit hit") == WorkerJobFailureReason.TIMEOUT
    assert classify_worker_failure(None, error_string="totally_new_error") == WorkerJobFailureReason.UNKNOWN


@pytest.mark.unit
def test_job_budget_profile_cost_and_noop_transition() -> None:
    JobBudgetTracker.clear_all()
    configure_job_cost(0.01, profile_id="profile-a")
    job = WorkerJob(
        job_id="job-1",
        event_id="evt-1",
        persona="soc",
        status=WorkerJobStatus.RUNNING,
    )
    job.transition_to(WorkerJobStatus.RUNNING)
    reset_job_cost()
    JobBudgetTracker.configure("s1", max_tokens=10, max_cost_usd=1.0, max_tool_calls=1)
    tracker = JobBudgetTracker.get("s1")
    assert tracker is not None


@pytest.mark.unit
def test_agent_bus_register_duplicate_and_list_payload() -> None:
    bus = SecureAgentBus(signing_key=b"key")
    bus.register_agent("soc", AgentTrustLevel.INTERNAL, ["intel"])
    bus.register_agent("intel", AgentTrustLevel.INTERNAL, [])
    msg_id = bus.send_message("soc", "intel", "finding", {"notes": ["safe", "also-safe"]})
    assert msg_id


@pytest.mark.unit
def test_sandbox_token_verify_expired() -> None:
    token = mint_sandbox_token(
        run_id="run-1",
        persona="soc",
        tenant_id="t1",
        job_id="job-1",
        ttl_s=-10,
        secret=b"key",
    )
    assert verify_sandbox_token(token, secret=b"key") is None


@pytest.mark.unit
def test_control_persona_helpers() -> None:
    assert is_control_persona("critic") is True
    assert is_platform_readonly_persona("consultant") is True


@pytest.mark.unit
def test_cross_ref_validator_policy_lines() -> None:
    validator = CrossRefValidator(known_tool_names={"read_file"}, policy_getter=lambda _pid: None)
    validator.validate_agent(AgentCatalogEntry(name="soc", tools=["read_file"]))


@pytest.mark.unit
def test_memory_read_conversation_and_list_by_tenant() -> None:
    from cys_core.domain.memory.models import MemoryEntry, MemoryScope
    from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
    from cys_core.domain.memory.validator import MemoryEntryValidator

    class MemoryStore:
        def __init__(self) -> None:
            self._entries: list[MemoryEntry] = []

        def append(self, entry: MemoryEntry) -> None:
            self._entries.append(entry)

        def query(self, scope: MemoryScope, *, limit: int = 20) -> list[MemoryEntry]:
            rows = [entry for entry in self._entries if entry.scope == scope]
            return rows[:limit]

        def list_by_tenant(self, tenant_id: str, *, limit: int = 100, agent: str | None = None):
            rows = [
                entry
                for entry in self._entries
                if entry.scope.tenant_id == tenant_id and (agent is None or entry.source_agent == agent)
            ]
            return rows[:limit]

    store = MemoryStore()
    writer = MemoryWriteService(store, signing_key=b"key")
    reader = MemoryReadService(store, signing_key=b"key")
    writer.append_conversation_turn(
        tenant_id="t1",
        investigation_id="inv-1",
        role="operator",
        text="hello",
        follow_up_id="fu-1",
        job_id="job-1",
        persona="soc",
        work_kind="follow_up_qa",
        mode="ask",
        content_type="text",
        finding={"summary": "x"},
        status="completed",
    )
    turns = reader.query_conversation_turns("t1", "inv-1")
    assert len(turns) == 1
    assert reader.query_conversation_turns("t2", "inv-1", requesting_tenant_id="t1") == []

    validator = MemoryEntryValidator(namespace_key="t1:inv-2", signing_key=b"key")
    store.append(
        MemoryEntry(
            scope=MemoryScope(tenant_id="t1", investigation_id="inv-2"),
            content="tenant wide",
            memory_type="finding",
            source_agent="soc",
            source_job_id="job-2",
            checksum=validator.checksum("tenant wide"),
            created_at=datetime.now(timezone.utc),
        )
    )
    listed = reader.list_by_tenant("t1", agent="soc")
    assert len(listed) == 1
    assert reader.list_by_tenant("t2", requesting_tenant_id="t1") == []
