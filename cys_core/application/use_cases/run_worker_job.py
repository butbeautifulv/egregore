from __future__ import annotations

import structlog
from typing import Any

from cys_core.application.ports.agent_registry import AgentRegistryPort
from cys_core.application.ports.sandbox import SandboxConnector
from cys_core.application.workers.agent_executor import WorkerAgentExecutor
from cys_core.application.workers.context_builder import WorkerContextBuilder
from cys_core.application.workers.finding_publisher import WorkerFindingPublisher
from cys_core.application.workers.evidence_gate import soc_evidence_gaps
from cys_core.application.workers.finding_quality import (
    consultant_finding_gaps,
    finding_meets_minimum,
    has_planned_tool_calls,
)
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_merged_manifest,
    get_tool_execution_count,
    get_tool_outputs,
    tool_succeeded,
)
from cys_core.application.workers.timeout_salvage import build_salvage_finding
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.sanitizer import InputSanitizer
from cys_core.domain.workers.exceptions import JobBudgetExceeded
from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.application.ports.tracing_ports import WorkerTracingPort
from cys_core.domain.workers.models import RunResult, WorkerJob

logger = structlog.get_logger(__name__)


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
    ) -> None:
        self._context_builder = context_builder
        self._agent_executor = agent_executor
        self._result_validator = result_validator
        self._finding_publisher = finding_publisher
        self._job_finalizer = job_finalizer
        self._registry = registry
        self.sandbox = sandbox
        self.sanitizer = sanitizer
        self._worker_tracing = worker_tracing
        self.use_tool_gateway = use_tool_gateway
        self.resolve_mcp_tools = resolve_mcp_tools
        self.resolve_legacy_tools = resolve_legacy_tools
        self.make_load_skill_tool = make_load_skill_tool

    def _mark_persona_completed(self, job: WorkerJob) -> None:
        self._job_finalizer.mark_persona_completed(job)

    async def mark_job_timeout(self, job: WorkerJob) -> None:
        await self._job_finalizer.mark_runtime_failure(job, "worker_job_timeout")

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
            if tools_executed >= 6:
                return f"{sanitized}{_EMIT_FINDING_NUDGE}"
        if job.persona == "intel":
            if tool_succeeded(job.job_id, "enrich_ioc") or tool_succeeded(
                job.job_id, "ti_search_in_category"
            ):
                return f"{sanitized}{_INTEL_FINDING_NUDGE}"
            if tools_executed >= 5:
                return f"{sanitized}{_INTEL_HARD_NUDGE}"
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
        )
        if salvage is None:
            return None
        defn = self._registry.get(job.persona)
        validated = self._result_validator.validate(
            result=salvage, schema_name=defn.schema_name or ""
        )
        result = validated if isinstance(validated, dict) else {"raw": validated}
        investigation_id = self._context_builder.investigation_id(job)
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
            is_final_report=False,
        )
        self._finding_publisher.persist_memory(job=job, result=result, investigation_id=investigation_id)
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

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        run_id = job.job_id
        investigation_id = self._context_builder.investigation_id(job)
        with self._worker_tracing.span(
            "worker.process_job",
            persona=job.persona,
            job_id=job.job_id,
            engagement_id=investigation_id,
            correlation_id=job.correlation_id,
            tenant_id=job.tenant_id,
        ):
            creds = None
            try:
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

                raw_input = self._context_builder.job_input(job)
                sanitized = self.sanitizer.sanitize(raw_input, source="external")
                defn = self._registry.get(job.persona)
                if job.persona == "consultant" and not (defn.schema_name or "").strip():
                    logger.warning(
                        "consultant_missing_output_schema",
                        job_id=job.job_id,
                        engagement_id=investigation_id,
                    )
                profile_id = resolve_profile_id(payload=job.payload, catalog_entry=defn)
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

                inv_ctx = self._context_builder.build(job)
                prior = inv_ctx.get("prior_findings") or []
                prompt = sanitized
                planned_tool_calls = False
                result: dict[str, Any] = {}
                with self._worker_tracing.span(
                    "worker.agent.run",
                    persona=job.persona,
                    job_id=job.job_id,
                    engagement_id=investigation_id,
                    tenant_id=job.tenant_id,
                ):
                    for attempt in range(3):
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

                if is_noop_finding(result):
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

                if not finding_meets_minimum(
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
                    raw_text = str(
                        result.get("raw")
                        or result.get("raw_response")
                        or result.get("summary")
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
                    if job.persona == "consultant":
                        gaps = consultant_finding_gaps(result)
                        if gaps:
                            raise ValueError(f"empty_finding:{','.join(gaps)}")
                    if job.persona == "soc":
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
                    raise ValueError("empty_finding")

                self._finding_publisher.append_engagement_finding(
                    job=job,
                    result=result,
                    investigation_id=investigation_id,
                    is_final_report=job.payload.get("phase") == "synthesis",
                )
                self._finding_publisher.persist_memory(job=job, result=result, investigation_id=investigation_id)
                if job.payload.get("phase") == "synthesis":
                    self._finding_publisher.publish_final_report(
                        job=job,
                        result=result,
                        investigation_id=investigation_id,
                    )
                else:
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
            except JobBudgetExceeded as exc:
                job_state["status"] = "error"
                self._job_finalizer.mark_budget_failure(job)
                return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
            except SecurityViolation as exc:
                job_state["status"] = "error"
                self._job_finalizer.mark_security_failure(job)
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
                await self._job_finalizer.mark_runtime_failure(job, str(exc))
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
