from __future__ import annotations

import structlog
from typing import Any

from cys_core.application.ports.agent_registry import AgentRegistryPort
from cys_core.application.ports.sandbox import SandboxConnector
from cys_core.application.workers.agent_executor import WorkerAgentExecutor
from cys_core.application.workers.context_builder import WorkerContextBuilder
from cys_core.application.workers.finding_publisher import WorkerFindingPublisher
from cys_core.application.workers.finding_quality import finding_meets_minimum
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.application.workers.noop_finding import is_noop_finding
from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.sanitizer import InputSanitizer
from cys_core.domain.workers.exceptions import JobBudgetExceeded
from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.application.ports.tracing_ports import WorkerTracingPort
from cys_core.domain.workers.models import RunResult, WorkerJob

logger = structlog.get_logger(__name__)


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
                with self._worker_tracing.span(
                    "worker.agent.run",
                    persona=job.persona,
                    job_id=job.job_id,
                    engagement_id=investigation_id,
                    tenant_id=job.tenant_id,
                ):
                    result = await self._agent_executor.run(
                        job=job,
                        sanitized=sanitized,
                        session_id=session_id,
                        sandbox_tools=sandbox_tools,
                        investigation_id=investigation_id,
                        profile_id=profile_id,
                        sandbox_id=creds.sandbox_id,
                        prior_findings_count=len(prior),
                    )
                    result = await self._agent_executor.self_refine(
                        job, sanitized, result, session_id=session_id
                    )

                result = self._result_validator.validate(result=result, schema_name=defn.schema_name or "")

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
                    self._job_finalizer.mark_persona_completed(job)
                    await self._job_finalizer.mark_success(job, investigation_id)
                    return RunResult(
                        job_id=job.job_id,
                        persona=job.persona,
                        success=True,
                        finding=result,
                        sandbox_id=creds.sandbox_id,
                    )

                if not finding_meets_minimum(job.persona, result, schema_name=defn.schema_name or None):
                    raise ValueError("empty_finding")

                self._finding_publisher.append_engagement_finding(
                    job=job, result=result, investigation_id=investigation_id
                )
                self._finding_publisher.persist_memory(job=job, result=result, investigation_id=investigation_id)
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
