from __future__ import annotations

import asyncio
from typing import Any

import structlog

from cys_core.application.ports.agent_registry import AgentRegistryPort
from cys_core.application.ports.metrics import MetricsPort
from cys_core.application.ports.sandbox import SandboxConnector
from cys_core.application.ports.tracing_ports import WorkerTracingPort
from cys_core.application.ports.workspace_store import WorkspaceStorePort
from cys_core.application.runtime_config import get_worker_max_attempts, get_worker_triage_max_attempts
from cys_core.application.use_cases.plan_follow_up import PlanFollowUpRunner
from cys_core.application.workers.agent_executor import WorkerAgentExecutor
from cys_core.application.workers.context_builder import WorkerContextBuilder
from cys_core.application.workers.evidence_gate import soc_evidence_gaps
from cys_core.application.workers.finding_publisher import WorkerFindingPublisher, should_publish_finding_to_bus
from cys_core.application.workers.finding_quality import (
    coerce_consultant_advisory_result,
    consultant_finding_gaps,
    finding_meets_minimum,
    follow_up_answer_gaps,
    has_planned_tool_calls,
)
from cys_core.application.workers.follow_up_aggregator import FollowUpAggregator
from cys_core.application.workers.follow_up_publisher import FollowUpAnswerPublisher, prepare_follow_up_result
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.application.workers.timeout_salvage import build_salvage_finding
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_merged_manifest,
    get_persona_manifests,
    get_tool_execution_count,
    get_tool_outputs,
    hydrate_job_from_snapshot,
    seed_job_from_persona_manifest,
    tool_succeeded,
)
from cys_core.application.workspace.persona_resolver import resolve_worker_agent_definition
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.evidence.coercion import coerce_sparse_soc_finding
from cys_core.domain.follow_up.models import (
    is_follow_up_orchestrator,
    is_follow_up_plan_planner_job,
    work_kind_from_payload,
)
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.sanitizer import InputSanitizer
from cys_core.domain.workers.bus_job_ids import is_bus_worker_job_id
from cys_core.domain.workers.exceptions import JobBudgetExceeded
from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.domain.workers.models import RunResult, WorkerJob

logger = structlog.get_logger(__name__)

_TRIAGE_PERSONAS = frozenset({"soc", "intel"})


def _is_recursion_limit_error(exc: BaseException) -> bool:
    return "Recursion limit" in str(exc)

_TOOL_RETRY_NUDGE = (
    "\n\n[System] Invoke tools through native tool calling only — do not emit JSON with "
    "'tool_calls'. After running SIEM/Veil tools, return the persona finding JSON."
)

_SIEM_FINDING_NUDGE = (
    "\n\n[System] investigate_incident succeeded. Emit SocFinding JSON now citing "
    "evidence_manifest observations via evidence[].obs_id refs. "
    "If manifest.telemetry_level is sparse or metadata_only, populate data_gaps from "
    "manifest and set confidence <= manifest.max_confidence. "
    "Do not assert process/account/pipe/PID details without matching observations."
)

_SIEM_GROUNDING_RETRY_NUDGE = (
    "\n\n[System] Previous SocFinding failed evidence grounding: {gaps}. "
    "Remove ungrounded claims. Cite only obs_id values from evidence_manifest. "
    "Populate data_gaps from manifest and cap confidence <= manifest.max_confidence."
)

_EMIT_FINDING_NUDGE = (
    "\n\n[System] Tool budget is nearly exhausted. "
    "Emit the persona finding JSON now with a non-empty summary field. "
    "Do not call any more tools."
)

_INTEL_FINDING_NUDGE = (
    "\n\n[System] TI enrichment succeeded. "
    "Emit IntelFinding JSON now with summary and iocs fields populated. "
    "Do not call more Veil tools."
)

_INTEL_HARD_NUDGE = (
    "\n\n[System] Intel tool budget exhausted. "
    "Return IntelFinding JSON immediately using data already collected."
)

_CONSULTANT_FINDING_NUDGE = (
    "\n\n[System] load_skill/playbook_search complete. "
    "Emit ConsultantFinding JSON now: topic, summary, "
    "at least 2 recommendations, confidence."
)


class RunWorkerJob:
    """Coordinate worker pipeline: sandbox → agent → publish → finalize."""

    def __init__(
        self,
        *,
        context_builder: WorkerContextBuilder,
        agent_executor: WorkerAgentExecutor,
        result_validator: WorkerResultValidator,
        finding_publisher: WorkerFindingPublisher,
        job_finalizer: WorkerJobFinalizer,
        registry: AgentRegistryPort,
        sandbox: SandboxConnector,
        sanitizer: InputSanitizer,
        worker_tracing: WorkerTracingPort,
        use_tool_gateway: bool,
        resolve_mcp_tools: Any,
        resolve_legacy_tools: Any,
        make_load_skill_tool: Any,
        follow_up_publisher: FollowUpAnswerPublisher | None = None,
        follow_up_aggregator: FollowUpAggregator | None = None,
        plan_follow_up_runner: PlanFollowUpRunner | None = None,
        workspace_store: WorkspaceStorePort | None = None,
        metrics: MetricsPort | None = None,
        build_job_trace_metadata: Any | None = None,
    ) -> None:
        self._context_builder = context_builder
        self._agent_executor = agent_executor
        self._result_validator = result_validator
        self._finding_publisher = finding_publisher
        self._follow_up_publisher = follow_up_publisher
        self._follow_up_aggregator = follow_up_aggregator
        self._plan_follow_up_runner = plan_follow_up_runner
        self._job_finalizer = job_finalizer
        self._registry = registry
        self.sandbox = sandbox
        self.sanitizer = sanitizer
        self._worker_tracing = worker_tracing
        self.use_tool_gateway = use_tool_gateway
        self.resolve_mcp_tools = resolve_mcp_tools
        self.resolve_legacy_tools = resolve_legacy_tools
        self.make_load_skill_tool = make_load_skill_tool
        self._workspace_store = workspace_store
        self._metrics = metrics
        self._build_job_trace_metadata = build_job_trace_metadata

    def _workspace_id_for_job(self, job: WorkerJob, investigation_id: str) -> str:
        store = self._context_builder._engagement_store
        if store is None:
            return ""
        engagement = store.get(job.tenant_id, investigation_id)
        if engagement is None:
            return ""
        return (getattr(engagement, "workspace_id", "") or "").strip()

    def _resolve_defn(self, job: WorkerJob, investigation_id: str):
        workspace_id = self._workspace_id_for_job(job, investigation_id)
        if not workspace_id or self._workspace_store is None:
            return self._registry.get(job.persona)
        try:
            return resolve_worker_agent_definition(
                persona=job.persona,
                workspace_id=workspace_id,
                registry=self._registry,
                workspace_store=self._workspace_store,
            )
        except Exception:
            return self._registry.get(job.persona)

    def _mark_persona_completed(self, job: WorkerJob) -> None:
        self._job_finalizer.mark_persona_completed(job)

    async def mark_job_timeout(self, job: WorkerJob) -> None:
        await self._job_finalizer.mark_runtime_failure(job, "worker_job_timeout", exc=TimeoutError())

    # NOTE(evidence-grounding-consolidation, 2026-07-14): uses `get_merged_manifest(job.job_id)`
    # (job-keyed), while process_finding_critic._structural_issues reads
    # `get_persona_manifests(investigation_id).get(persona)` for the same finding once it reaches
    # the critic. See the detailed rationale above `record_evidence_manifest` in
    # cys_core/application/workers/tool_execution_tracker.py for why these two lookups were
    # deliberately NOT unified (both are process-local in-memory state; the worker and critic run
    # as separate processes in every real deployment topology here).
    def _apply_soc_sparse_coerce(self, job: WorkerJob, result: dict[str, Any], investigation_id: str) -> bool:
        if job.persona != "soc":
            return False
        manifest = get_merged_manifest(job.job_id)
        if manifest is None:
            return False
        coerced = coerce_sparse_soc_finding(result, manifest)
        if coerced:
            logger.info(
                "worker_grounding_coerced",
                job_id=job.job_id,
                persona=job.persona,
                engagement_id=investigation_id,
            )
        return coerced

    def _retry_nudge(
        self,
        job: WorkerJob,
        sanitized: str,
        *,
        attempt: int,
        planned_tool_calls: bool,
        tools_executed: int,
        grounding_gaps: list[str] | None = None,
    ) -> str | None:
        if attempt >= 2:
            return None
        if grounding_gaps:
            return f"{sanitized}{_SIEM_GROUNDING_RETRY_NUDGE.format(gaps=', '.join(grounding_gaps))}"
        if attempt == 0 and planned_tool_calls and tools_executed == 0:
            return f"{sanitized}{_TOOL_RETRY_NUDGE}"
        if job.persona == "soc":
            if tool_succeeded(job.job_id, "investigate_incident"):
                return f"{sanitized}{_SIEM_FINDING_NUDGE}"
            if tools_executed >= 4:
                return f"{sanitized}{_EMIT_FINDING_NUDGE}"
        if job.persona == "intel":
            if tool_succeeded(job.job_id, "enrich_ioc") or tool_succeeded(
                job.job_id, "ti_search_in_category"
            ):
                return f"{sanitized}{_INTEL_FINDING_NUDGE}"
            if tools_executed >= 4:
                return f"{sanitized}{_INTEL_HARD_NUDGE}"
        if job.persona == "consultant":
            if tool_succeeded(job.job_id, "load_skill"):
                return f"{sanitized}{_CONSULTANT_FINDING_NUDGE}"
            if tools_executed >= 4:
                return f"{sanitized}{_EMIT_FINDING_NUDGE}"
        return None

    async def try_salvage_partial(
        self,
        job: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
        *,
        reason: str = "worker_job_timeout",
    ) -> RunResult | None:
        """Publish a partial finding from cached tool outputs when budget is exhausted."""
        outputs = get_tool_outputs(job.job_id)
        salvage = build_salvage_finding(
            job.persona,
            outputs,
            job_id=job.job_id,
            salvage_reason=reason,
            goal=str(job.payload.get("goal") or ""),
        )
        if salvage is None:
            return None
        investigation_id = self._context_builder.investigation_id(job)
        defn = self._resolve_defn(job, investigation_id)
        validated = self._result_validator.validate(
            result=salvage, schema_name=defn.schema_name or ""
        )
        result = validated if isinstance(validated, dict) else {"raw": validated}
        if not finding_meets_minimum(
            job.persona,
            result,
            schema_name=defn.schema_name or None,
            job_id=job.job_id,
            investigation_id=investigation_id,
        ):
            return None

        logger.warning(
            "worker_partial_salvaged",
            job_id=job.job_id,
            persona=job.persona,
            engagement_id=investigation_id,
            tool_outputs=len(outputs),
            salvage_reason=reason,
        )
        self._finding_publisher.append_engagement_finding(
            job=job,
            result=result,
            investigation_id=investigation_id,
            defn=defn,
        )
        self._finding_publisher.persist_memory(job=job, result=result, investigation_id=investigation_id)
        if should_publish_finding_to_bus(persona=job.persona, role=getattr(defn, "role", None)):
            await self._finding_publisher.publish(
                job=job,
                defn=defn,
                result=result,
                sandbox_id=job.sandbox_id or "",
                investigation_id=investigation_id,
            )
        budget_state = JobBudgetTracker.get(session_id)
        if budget_state is not None:
            job.payload["estimated_cost_usd"] = budget_state.cost_usd
        job.payload["salvaged_finding"] = True
        if job.payload.get("phase") != "synthesis":
            self._job_finalizer.mark_persona_completed(job)
        job_state["status"] = "success"
        await self._job_finalizer.mark_success(job, investigation_id)
        if self._metrics is not None:
            self._metrics.record_worker_job_salvaged(job.persona, reason)
        return RunResult(
            job_id=job.job_id,
            persona=job.persona,
            success=True,
            finding=result,
            sandbox_id=job.sandbox_id or "",
        )

    async def try_salvage_timeout(
        self,
        job: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult | None:
        """Backward-compatible alias for wall-clock timeout salvage."""
        return await self.try_salvage_partial(
            job,
            session_id,
            job_state,
            reason="worker_job_timeout",
        )

    async def _execute_follow_up_plan_planner(
        self, plan_follow_up_runner: PlanFollowUpRunner, job: WorkerJob, investigation_id: str, session_id: str
    ) -> RunResult:
        try:
            self._job_finalizer.mark_running(job, session_id)
            self._job_finalizer.publish_job_started(job, investigation_id)
            result = await plan_follow_up_runner.execute(job, investigation_id)
            await self._job_finalizer.mark_success(job, investigation_id)
            return RunResult(
                job_id=job.job_id,
                persona=job.persona,
                success=True,
                finding=result,
                sandbox_id="",
            )
        except Exception as exc:
            if self._follow_up_publisher is not None:
                self._follow_up_publisher.publish_failure(
                    job=job,
                    investigation_id=investigation_id,
                    error=str(exc),
                )
            await self._job_finalizer.mark_runtime_failure(job, str(exc), exc=exc)
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))

    async def _execute_resume(self, job: WorkerJob, investigation_id: str) -> RunResult:
        """Continue an interrupted LangGraph thread after HITL approval.

        Deliberately does not go through _publish_and_finalize()'s synthesis/
        follow-up branching — those depend on the original job's payload
        (goal/phase/findings_summary), which this job structurally doesn't
        have (job_store only carries lightweight metadata, not the original
        payload — Discovery G, docs/MICROSERVICES_SPLIT_PHASES_DETAIL.md).
        The LangGraph checkpoint itself already encodes what phase the
        interrupted run was in; this only needs to unblock it and publish
        whatever it produces, the same way any non-synthesis finding is
        published. Creates a fresh sandbox scoped to *this* resume job's own
        run_id — giving Command(resume=...) real MCP Tool Gateway credentials
        if the graph goes on to call more tools, which the inline
        runtime.aresume() call this replaces never did (Discovery B).
        """
        run_id = job.job_id
        creds = None
        try:
            creds = await self._create_sandbox(job, run_id, investigation_id, job.resume_checkpoint_ref)
            defn = self._resolve_defn(job, investigation_id)
            resume_payload = {
                "decision": job.payload.get("decision"),
                "approval_id": job.payload.get("approval_id"),
            }
            result = await self._agent_executor.resume(
                persona=job.persona,
                session_id=job.resume_checkpoint_ref,
                resume_payload=resume_payload,
            )
            await self._finding_publisher.publish(
                job=job,
                defn=defn,
                result=result,
                sandbox_id=creds.sandbox_id,
                investigation_id=investigation_id,
            )
            await self._job_finalizer.mark_success(job, investigation_id)
            return RunResult(
                job_id=job.job_id,
                persona=job.persona,
                success=True,
                finding=result,
                sandbox_id=creds.sandbox_id,
            )
        except Exception as exc:
            await self._job_finalizer.mark_runtime_failure(job, str(exc), exc=exc)
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
        finally:
            with self._worker_tracing.span(
                "worker.sandbox.destroy",
                persona=job.persona,
                job_id=job.job_id,
                engagement_id=investigation_id,
                tenant_id=job.tenant_id,
            ):
                await self.sandbox.adestroy(run_id)

    def _seed_bus_or_follow_up_manifest(self, job: WorkerJob, investigation_id: str) -> None:
        if job.feedback or is_bus_worker_job_id(job.job_id):
            manifest = get_persona_manifests(investigation_id).get(job.persona)
            if manifest is not None:
                seed_job_from_persona_manifest(job.job_id, manifest, mark_siem_done=True)
        if work_kind_from_payload(job.payload) == "follow_up_child":
            snapshot = job.payload.get("evidence_snapshot")
            if snapshot is not None:
                hydrate_job_from_snapshot(job.job_id, snapshot)
            else:
                manifest = get_persona_manifests(investigation_id).get(job.persona)
                if manifest is not None:
                    seed_job_from_persona_manifest(job.job_id, manifest, mark_siem_done=True)

    def _build_job_span_attrs(self, job: WorkerJob, investigation_id: str, inv_ctx: dict) -> dict:
        if self._build_job_trace_metadata is None:
            return {}
        trace_meta = self._build_job_trace_metadata(
            persona=job.persona,
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            investigation_id=investigation_id,
            tenant_id=job.tenant_id,
            workspace_id=str(inv_ctx.get("workspace_id", "") or ""),
            sandbox_id=job.sandbox_id,
            memory_entries_loaded=len(inv_ctx.get("prior_findings") or []),
        )
        return trace_meta.get("metadata", {})

    async def _create_sandbox(self, job: WorkerJob, run_id: str, investigation_id: str, session_id: str):
        # NOTE(k8s-sandbox-followup, backlog Q2-1): `sandbox.acreate()` provisions and
        # (for K8sSandboxConnector) genuinely waits for the sandbox resource to be
        # ready, failing closed instead of silently falling back to unsandboxed
        # execution — see cys_core/infrastructure/k8s_sandbox.py docstring. The agent
        # LLM/tool loop below (`_run_agent_with_retries`) still runs in *this* process,
        # not inside the sandbox's container/pod; tool calls are routed to it via the
        # MCP Tool Gateway bound to `creds.sandbox_id` instead. Moving the agent loop
        # itself into the sandboxed pod (dispatcher pattern) is the remaining piece of
        # Q2-1, not done here.
        with self._worker_tracing.span(
            "worker.sandbox.create",
            persona=job.persona,
            job_id=job.job_id,
            engagement_id=investigation_id,
            tenant_id=job.tenant_id,
        ):
            creds = await self.sandbox.acreate(run_id, job.persona)
        job.sandbox_id = creds.sandbox_id
        self._job_finalizer.mark_running(job, session_id)
        self._job_finalizer.publish_job_started(job, investigation_id)
        return creds

    def _prepare_agent_inputs(self, job: WorkerJob, investigation_id: str, inv_ctx: dict, creds):
        raw_input = self._context_builder.job_input(job)
        sanitized = self.sanitizer.sanitize(raw_input, source="external")
        defn = self._resolve_defn(job, investigation_id)
        if job.persona == "consultant" and not (defn.schema_name or "").strip():
            logger.warning(
                "consultant_missing_output_schema",
                job_id=job.job_id,
                engagement_id=investigation_id,
            )
        profile_id = resolve_profile_id(payload=job.payload, catalog_entry=defn)
        workspace_id = str(inv_ctx.get("workspace_id", "") or "")
        sandbox_tools: list = []
        if self.use_tool_gateway:
            sandbox_tools.extend(
                self.resolve_mcp_tools(
                    defn.tools,
                    creds.sandbox_id,
                    persona=job.persona,
                    job_id=job.job_id,
                    correlation_id=job.correlation_id,
                    profile_id=profile_id,
                    workspace_id=workspace_id,
                )
            )
        else:
            sandbox_tools.extend(self.resolve_legacy_tools(defn.tools))
        if defn.skills:
            sandbox_tools.append(
                self.make_load_skill_tool(
                    defn.skills,
                    persona=job.persona,
                    job_id=job.job_id,
                    investigation_id=investigation_id,
                    tenant_id=job.tenant_id,
                )
            )
        return sanitized, defn, profile_id, sandbox_tools

    async def _run_agent_with_retries(
        self,
        job: WorkerJob,
        sanitized: str,
        session_id: str,
        sandbox_tools: list,
        investigation_id: str,
        profile_id: str,
        creds,
        prior: list,
        defn,
    ) -> tuple[dict[str, Any], bool]:
        prompt = sanitized
        planned_tool_calls = False
        result: dict[str, Any] = {}
        # NOTE: this span previously only wrapped the `max_attempts` assignment due to a
        # dedent bug, leaving the actual agent run (LLM + tool calls, all retries) untraced.
        with self._worker_tracing.span(
            "worker.agent.run",
            persona=job.persona,
            job_id=job.job_id,
            engagement_id=investigation_id,
            tenant_id=job.tenant_id,
        ):
            max_attempts = (
                get_worker_triage_max_attempts()
                if job.persona in _TRIAGE_PERSONAS
                else get_worker_max_attempts()
            )
            for attempt in range(max_attempts):
                result = await self._agent_executor.run(
                    job=job,
                    sanitized=prompt,
                    session_id=session_id,
                    sandbox_tools=sandbox_tools,
                    investigation_id=investigation_id,
                    profile_id=profile_id,
                    sandbox_id=creds.sandbox_id,
                    prior_findings_count=len(prior),
                )
                result = await self._agent_executor.self_refine(
                    job, prompt, result, session_id=session_id
                )
                planned_tool_calls = (
                    has_planned_tool_calls(result) if isinstance(result, dict) else False
                )
                validated = self._result_validator.validate(
                    result=result, schema_name=defn.schema_name or ""
                )
                result = validated if isinstance(validated, dict) else {"raw": validated}
                self._apply_soc_sparse_coerce(job, result, investigation_id)
                if finding_meets_minimum(
                    job.persona,
                    result,
                    schema_name=defn.schema_name or None,
                    job_id=job.job_id,
                    investigation_id=investigation_id,
                    phase=str(job.payload.get("phase", "")),
                    specialist_findings=job.payload.get("findings_summary")
                    if job.payload.get("phase") == "synthesis"
                    else None,
                ):
                    break
                grounding_gaps: list[str] | None = None
                if job.persona == "soc":
                    grounding_gaps = soc_evidence_gaps(result, get_merged_manifest(job.job_id))
                tools_executed = get_tool_execution_count(job.job_id)
                nudge = self._retry_nudge(
                    job,
                    sanitized,
                    attempt=attempt,
                    planned_tool_calls=planned_tool_calls,
                    tools_executed=tools_executed,
                    grounding_gaps=grounding_gaps,
                )
                if nudge is not None:
                    if planned_tool_calls and tools_executed == 0 and attempt == 0:
                        clear_tool_execution_count(job.job_id)
                        logger.info(
                            "worker_tool_retry",
                            job_id=job.job_id,
                            persona=job.persona,
                            engagement_id=investigation_id,
                        )
                    elif job.persona == "soc" and tool_succeeded(job.job_id, "investigate_incident"):
                        logger.info(
                            "worker_siem_finding_nudge",
                            job_id=job.job_id,
                            persona=job.persona,
                            engagement_id=investigation_id,
                        )
                    elif job.persona == "intel":
                        logger.info(
                            "worker_intel_finding_nudge",
                            job_id=job.job_id,
                            persona=job.persona,
                            engagement_id=investigation_id,
                            tools_executed=tools_executed,
                        )
                    elif job.persona == "consultant":
                        logger.info(
                            "worker_consultant_finding_nudge",
                            job_id=job.job_id,
                            persona=job.persona,
                            engagement_id=investigation_id,
                            tools_executed=tools_executed,
                        )
                    else:
                        logger.info(
                            "worker_emit_finding_nudge",
                            job_id=job.job_id,
                            persona=job.persona,
                            engagement_id=investigation_id,
                            tools_executed=tools_executed,
                        )
                    prompt = nudge
                    continue
                break
        return result, planned_tool_calls

    async def _handle_noop_finding(
        self, job: WorkerJob, result: dict, session_id: str, investigation_id: str, creds
    ) -> RunResult | None:
        if not is_noop_finding(result):
            return None
        logger.info(
            "worker_noop_finding_skipped",
            job_id=job.job_id,
            persona=job.persona,
            engagement_id=investigation_id,
        )
        self._finding_publisher.record_noop(job=job, investigation_id=investigation_id)
        budget_state = JobBudgetTracker.get(session_id)
        if budget_state is not None:
            job.payload["estimated_cost_usd"] = budget_state.cost_usd
        job.payload["noop_finding"] = True
        if job.payload.get("phase") != "synthesis":
            self._job_finalizer.mark_persona_completed(job)
        await self._job_finalizer.mark_success(job, investigation_id)
        return RunResult(
            job_id=job.job_id,
            persona=job.persona,
            success=True,
            finding=result,
            sandbox_id=creds.sandbox_id,
        )

    async def _handle_invalid_finding(
        self,
        job: WorkerJob,
        result: dict,
        planned_tool_calls: bool,
        session_id: str,
        job_state: dict[str, str],
        investigation_id: str,
    ) -> RunResult:
        """Diagnose why a finding failed `finding_meets_minimum` and raise the most
        specific error, or (intel only) return a salvaged partial result. Always
        raises or returns — never falls through."""
        raw_text = str(
            result.get("raw")
            or result.get("raw_response")
            or result.get("summary")
            or result.get("error")
            or ""
        ).strip()
        if raw_text and (
            "cannot process" in raw_text.lower()
            or "operational guidelines" in raw_text.lower()
            or "i can't" in raw_text.lower()
            or "i cannot" in raw_text.lower()
        ):
            raise ValueError(f"model_refusal:{raw_text[:240]}")
        tools_executed = get_tool_execution_count(job.job_id)
        if planned_tool_calls and tools_executed == 0:
            raise ValueError(
                "tools_not_executed:model returned planned tool_calls JSON "
                "without native tool invocations; call SIEM/Veil tools directly"
            )
        if job.persona == "consultant" and not is_follow_up_orchestrator(job.payload):
            gaps = consultant_finding_gaps(result)
            if gaps:
                raise ValueError(f"empty_finding:{','.join(gaps)}")
        if is_follow_up_orchestrator(job.payload):
            result = prepare_follow_up_result(job, result)
            gaps = follow_up_answer_gaps(result)
            if gaps:
                raise ValueError(f"empty_finding:{','.join(gaps)}")
        if job.persona == "soc":
            self._apply_soc_sparse_coerce(job, result, investigation_id)
            gaps = soc_evidence_gaps(result, get_merged_manifest(job.job_id))
            if gaps:
                logger.warning(
                    "worker_grounding_rejected",
                    job_id=job.job_id,
                    persona=job.persona,
                    engagement_id=investigation_id,
                    ungrounded_claims=gaps,
                )
                raise ValueError(f"ungrounded_finding:{','.join(gaps)}")
        if job.persona == "intel":
            salvaged = await self.try_salvage_partial(
                job,
                session_id,
                job_state,
                reason="empty_finding",
            )
            if salvaged is not None:
                return salvaged
        raise ValueError("empty_finding")

    async def _complete_follow_up_orchestrator(
        self, job: WorkerJob, result: dict, session_id: str, investigation_id: str, creds
    ) -> RunResult:
        if (
            work_kind_from_payload(job.payload) == "follow_up_orchestrate"
            and self._follow_up_aggregator is not None
        ):
            child_ids = self._follow_up_aggregator.spawned_child_ids(
                job.tenant_id,
                investigation_id,
                orchestrator_job_id=job.job_id,
            )
            if not child_ids:
                raw_children = job.payload.get("spawned_job_ids")
                if isinstance(raw_children, list):
                    child_ids = [str(item) for item in raw_children]
            if child_ids:
                await self._follow_up_aggregator.wait_for_children(child_ids)
                # merge_child_findings does blocking job_store/memory-store reads;
                # offload to a worker thread so it doesn't block the event loop
                # (same pattern used elsewhere in this codebase for sync I/O
                # inside async def, e.g. cys_core/infrastructure/k8s_sandbox.py).
                result = await asyncio.to_thread(
                    self._follow_up_aggregator.merge_child_findings,
                    result,
                    child_ids,
                    tenant_id=job.tenant_id,
                    investigation_id=investigation_id,
                )
        if self._follow_up_publisher is not None:
            self._follow_up_publisher.publish_success(
                job=job,
                result=result,
                investigation_id=investigation_id,
            )
        budget_state = JobBudgetTracker.get(session_id)
        if budget_state is not None:
            job.payload["estimated_cost_usd"] = budget_state.cost_usd
        if (
            work_kind_from_payload(job.payload) == "initial_qa"
            and isinstance(result, dict)
            and self._job_finalizer._engagement_store is not None
        ):
            from cys_core.application.findings.outcome_mapper import finding_to_operator_outcome

            outcome = finding_to_operator_outcome(result, kind="advisory")
            self._job_finalizer._engagement_store.set_final_report(
                job.tenant_id,
                investigation_id,
                outcome.to_final_report(),
            )
        await self._job_finalizer.mark_follow_up_success(job, investigation_id)
        return RunResult(
            job_id=job.job_id,
            persona=job.persona,
            success=True,
            finding=result,
            sandbox_id=creds.sandbox_id,
        )

    async def _publish_and_finalize(
        self, job: WorkerJob, result: dict, investigation_id: str, session_id: str, creds, defn
    ) -> RunResult:
        if job.payload.get("phase") != "synthesis":
            self._finding_publisher.append_engagement_finding(
                job=job,
                result=result,
                investigation_id=investigation_id,
                defn=defn,
            )
        self._finding_publisher.persist_memory(job=job, result=result, investigation_id=investigation_id)
        if job.payload.get("phase") == "synthesis":
            self._finding_publisher.publish_final_report(
                job=job,
                result=result,
                investigation_id=investigation_id,
            )
            follow_up_id = str(job.payload.get("follow_up_id", ""))
            if follow_up_id and self._follow_up_publisher is not None:
                engagement = None
                if self._job_finalizer._engagement_store is not None:
                    engagement = self._job_finalizer._engagement_store.get(
                        job.tenant_id, investigation_id
                    )
                plan_snapshot: dict[str, Any] = {
                    "summary": str(result.get("summary", result.get("finding", ""))),
                    "final_report": result,
                }
                if engagement is not None and engagement.planner_plan:
                    plan_snapshot["personas"] = list(engagement.planner_plan)
                    plan_snapshot["sub_goals"] = dict(engagement.planner_sub_goals or {})
                    plan_snapshot["rationale"] = engagement.planner_rationale
                synth_job = WorkerJob(
                    job_id=job.job_id,
                    event_id=job.event_id,
                    persona=job.persona,
                    correlation_id=job.correlation_id,
                    tenant_id=job.tenant_id,
                    payload={**job.payload, "work_kind": "follow_up_plan"},
                )
                self._follow_up_publisher.publish_success(
                    job=synth_job,
                    result=plan_snapshot,
                    investigation_id=investigation_id,
                )
                if engagement is not None:
                    engagement.close_after_follow_up()
                    if self._job_finalizer._engagement_store is not None:
                        self._job_finalizer._engagement_store.upsert(engagement)
        else:
            if should_publish_finding_to_bus(persona=job.persona, role=getattr(defn, "role", None)):
                await self._finding_publisher.publish(
                    job=job,
                    defn=defn,
                    result=result,
                    sandbox_id=creds.sandbox_id,
                    investigation_id=investigation_id,
                )

        budget_state = JobBudgetTracker.get(session_id)
        if budget_state is not None:
            job.payload["estimated_cost_usd"] = budget_state.cost_usd

        if job.payload.get("phase") != "synthesis":
            self._job_finalizer.mark_persona_completed(job)
        await self._job_finalizer.mark_success(job, investigation_id)

        return RunResult(
            job_id=job.job_id,
            persona=job.persona,
            success=True,
            finding=result,
            sandbox_id=creds.sandbox_id,
        )

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        run_id = job.job_id
        investigation_id = self._context_builder.investigation_id(job)

        if job.resume_checkpoint_ref:
            return await self._execute_resume(job, investigation_id)

        if is_follow_up_plan_planner_job(job.payload, persona=job.persona) and self._plan_follow_up_runner is not None:
            return await self._execute_follow_up_plan_planner(
                self._plan_follow_up_runner, job, investigation_id, session_id
            )

        self._seed_bus_or_follow_up_manifest(job, investigation_id)
        inv_ctx = self._context_builder.build(job)
        span_attrs = self._build_job_span_attrs(job, investigation_id, inv_ctx)

        with self._worker_tracing.span(
            "worker.process_job",
            **span_attrs,
        ):
            creds = None
            try:
                creds = await self._create_sandbox(job, run_id, investigation_id, session_id)
                sanitized, defn, profile_id, sandbox_tools = self._prepare_agent_inputs(
                    job, investigation_id, inv_ctx, creds
                )
                prior = inv_ctx.get("prior_findings") or []

                result, planned_tool_calls = await self._run_agent_with_retries(
                    job,
                    sanitized,
                    session_id,
                    sandbox_tools,
                    investigation_id,
                    profile_id,
                    creds,
                    prior,
                    defn,
                )

                noop_result = await self._handle_noop_finding(job, result, session_id, investigation_id, creds)
                if noop_result is not None:
                    return noop_result

                if (
                    job.persona == "consultant"
                    and not is_follow_up_orchestrator(job.payload)
                    and job.payload.get("phase") != "synthesis"
                ):
                    coerce_consultant_advisory_result(
                        result,
                        goal=str(inv_ctx.get("goal") or job.payload.get("goal") or ""),
                    )

                meets_minimum = True
                if not is_follow_up_orchestrator(job.payload):
                    meets_minimum = finding_meets_minimum(
                        job.persona,
                        result,
                        schema_name=defn.schema_name or None,
                        job_id=job.job_id,
                        investigation_id=investigation_id,
                        phase=str(job.payload.get("phase", "")),
                        specialist_findings=job.payload.get("findings_summary")
                        if job.payload.get("phase") == "synthesis"
                        else None,
                    )
                if not meets_minimum:
                    return await self._handle_invalid_finding(
                        job, result, planned_tool_calls, session_id, job_state, investigation_id
                    )

                if is_follow_up_orchestrator(job.payload):
                    return await self._complete_follow_up_orchestrator(
                        job, result, session_id, investigation_id, creds
                    )

                return await self._publish_and_finalize(job, result, investigation_id, session_id, creds, defn)
            except JobBudgetExceeded as exc:
                job_state["status"] = "error"
                salvaged = await self.try_salvage_partial(
                    job,
                    session_id,
                    job_state,
                    reason="budget_exceeded",
                )
                if salvaged is not None:
                    return salvaged
                await self._job_finalizer.mark_budget_failure(job, exc=exc)
                return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
            except SecurityViolation as exc:
                job_state["status"] = "error"
                await self._job_finalizer.mark_security_failure(job, exc=exc)
                return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
            except Exception as exc:
                if _is_recursion_limit_error(exc):
                    salvaged = await self.try_salvage_partial(
                        job,
                        session_id,
                        job_state,
                        reason="recursion_limit_exhausted",
                    )
                    if salvaged is not None:
                        return salvaged
                job_state["status"] = "error"
                await self._job_finalizer.mark_runtime_failure(job, str(exc), exc=exc)
                return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
            finally:
                with self._worker_tracing.span(
                    "worker.sandbox.destroy",
                    persona=job.persona,
                    job_id=job.job_id,
                    engagement_id=investigation_id,
                    tenant_id=job.tenant_id,
                ):
                    await self.sandbox.adestroy(run_id)
