from __future__ import annotations

import asyncio
from typing import Any

import structlog

from bootstrap.container import get_container
from bootstrap.settings import settings
from cys_core.application.bus_engagement import normalize_correlation_id
from cys_core.application.ports.agent_runner import AgentRunner
from cys_core.application.ports.execution_backend import ExecutionBackend
from cys_core.application.workers.tool_execution_tracker import (
    clear_tool_execution_count,
    get_tool_execution_count,
)
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.domain.workers.models import RunResult, WorkerJob
from cys_core.infrastructure.bus_transport import get_bus_transport
from cys_core.infrastructure.execution.in_process import InProcessExecutionBackend
from cys_core.infrastructure.policy.budget_adapter import enrich_job_budget
from cys_core.infrastructure.sandbox import get_sandbox_connector
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id
from cys_core.registry.agents import AgentRegistry, get_agent_registry

logger = structlog.get_logger(__name__)

_TRUST_MAP = {
    "untrusted": AgentTrustLevel.UNTRUSTED,
    "internal": AgentTrustLevel.INTERNAL,
    "privileged": AgentTrustLevel.PRIVILEGED,
    "system": AgentTrustLevel.SYSTEM,
}


def build_agent_bus(
    registry: AgentRegistry | None = None,
    signing_key: bytes | None = None,
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
) -> SecureAgentBus:
    key = signing_key if signing_key is not None else settings.bus_signing_key_bytes
    reg = registry or get_agent_registry()
    policy = get_container().get_profile_policy_port().get_policy(profile_id)
    bus = SecureAgentBus(signing_key=key, profile_id=profile_id, policy=policy)
    for defn in reg.all():
        bus.register_agent(
            defn.name,
            _TRUST_MAP.get(defn.trust_level, AgentTrustLevel.INTERNAL),
            defn.bus_recipients,
        )
    return bus


_MAX_DEPENDENCY_DEFERRALS = 10


def _max_dependency_deferrals() -> int:
    return get_container().settings.worker_max_dependency_deferrals


class WorkerOrchestrator:
    """Dequeue → budget → worker pipeline execution.

    Depends only on the `AgentRunner` port (docs/MICROSERVICES_SPLIT_PLAN.md §22.3/§22.4's
    `AgentRuntimePort`), never on `cys_core.runtime.agent`'s concrete `AgentRuntime`/`get_runtime`
    by import path — this is the dispatcher/agent_runtime seam. Which concrete implementation to
    use by default is a composition-root decision (`bootstrap/containers/engagement_container.py`),
    not this class's.
    """

    def __init__(
        self,
        *,
        runtime: AgentRunner,
        persona: str | None = None,
        bus: SecureAgentBus | None = None,
        registry: AgentRegistry | None = None,
        transport: Any = None,
        sanitizer: Any = None,
        execution_backend: ExecutionBackend | None = None,
    ) -> None:
        self.persona = persona
        self.runtime = runtime
        self.registry = registry or get_agent_registry()
        self.bus = bus or build_agent_bus(self.registry, signing_key=settings.bus_signing_key_bytes)
        container = get_container()
        self.sandbox = get_sandbox_connector()
        self.queue = container.get_job_queue(persona=persona)
        self.transport = transport or get_bus_transport()
        self.sanitizer = sanitizer or get_input_sanitizer()
        self._metrics = container.get_metrics_port()
        self.job_store = container.get_job_store()
        self._run_worker_job = container.get_run_worker_job(
            persona=persona,
            runtime=self.runtime,
            registry=self.registry,
            bus=self.bus,
            sandbox=self.sandbox,
            transport=self.transport,
            queue=self.queue,
            sanitizer=self.sanitizer,
        )
        self.execution_backend = execution_backend or InProcessExecutionBackend(self._run_worker_job)

    async def run_job(self, job: WorkerJob) -> RunResult:
        container = get_container()
        if job.depends_on_persona:
            investigation_id = normalize_correlation_id(
                job.correlation_id or job.event_id,
                job.payload,
            )
            state = container.get_engagement_state_store().get(job.tenant_id, investigation_id)
            completed = state.completed_personas if state is not None else []
            failed = state.failed_personas if state is not None else []
            if (
                job.depends_on_persona not in completed
                and job.depends_on_persona not in failed
            ):
                deferrals = int(job.payload.get("dependency_deferrals", 0))
                if deferrals >= _max_dependency_deferrals():
                    await self._run_worker_job.mark_runtime_failure(
                        job,
                        "dependency_timeout",
                        exc=TimeoutError("dependency_timeout"),
                    )
                    return RunResult(
                        job_id=job.job_id,
                        persona=job.persona,
                        success=False,
                        error="dependency_timeout",
                    )
                job.payload["dependency_deferrals"] = deferrals + 1
                enqueue_front = getattr(self.queue, "aenqueue_front", None)
                if enqueue_front is not None:
                    await enqueue_front(job)
                else:
                    await self.queue.aenqueue(job)
                return RunResult(
                    job_id=job.job_id,
                    persona=job.persona,
                    success=False,
                    error=f"dependency_not_ready:{job.depends_on_persona}",
                )

        budgeted = enrich_job_budget(job)
        run_id = job.job_id
        session_id = f"worker:{job.persona}:{run_id}"
        investigation_id = normalize_correlation_id(job.correlation_id or job.event_id, job.payload)
        cid_token = bind_correlation_id(investigation_id)
        structlog.contextvars.bind_contextvars(
            persona=job.persona,
            job_id=job.job_id,
            correlation_id=investigation_id,
            work_kind=str(job.payload.get("work_kind", "")),
        )
        from cys_core.domain.workers.job_budget import configure_job_cost
        from cys_core.infrastructure.policy.budget_adapter import resolve_job_cost_context

        profile_id, cost_rate = resolve_job_cost_context(
            budgeted, default_cost_rate=container.settings.job_cost_per_1k_tokens_usd
        )
        configure_job_cost(cost_rate, profile_id=profile_id)
        JobBudgetTracker.configure(
            session_id,
            max_tokens=budgeted.max_tokens,
            max_cost_usd=budgeted.max_cost_usd,
            max_tool_calls=budgeted.max_tool_calls,
            profile_id=profile_id,
        )
        try:
            with self._metrics.track_worker_job(job.persona) as job_state:
                job_timeout = container.settings.resolve_worker_job_timeout(
                    persona=job.persona,
                    phase=str(job.payload.get("phase") or ""),
                )
                soft_timeout = job_timeout * container.settings.worker_soft_timeout_fraction
                backend_owns_timeout = getattr(self.execution_backend, "owns_timeout", False)
                wait_timeout = job_timeout if backend_owns_timeout else soft_timeout
                try:
                    return await asyncio.wait_for(
                        self.execution_backend.execute(job, budgeted, session_id, job_state),
                        timeout=wait_timeout,
                    )
                except TimeoutError:
                    if backend_owns_timeout:
                        # Backend (subprocess/K8s/Docker) manages its own soft-timeout
                        # and salvage inside the child process, where the live
                        # tool_execution_tracker/JobBudgetTracker state actually is
                        # (Discoveries A/D). Reaching here means the child overran even
                        # the hard job_timeout — a dead-man's switch, not the normal
                        # path — so there is nothing in this process to salvage.
                        logger.error(
                            "worker job exceeded hard timeout without returning",
                            job_id=job.job_id,
                            persona=job.persona,
                            job_timeout_s=job_timeout,
                        )
                        self._metrics.record_worker_job_timeout(job.persona)
                        await self._run_worker_job.mark_job_timeout(job)
                        return RunResult(
                            job_id=job.job_id,
                            persona=job.persona,
                            success=False,
                            error="worker_job_timeout",
                        )
                    tool_count = get_tool_execution_count(job.job_id)
                    salvaged: RunResult | None = None
                    try:
                        salvaged = await self._run_worker_job.try_salvage_partial(
                            job,
                            session_id,
                            job_state,
                            reason="soft_timeout",
                        )
                    except Exception as exc:
                        logger.warning(
                            "worker_soft_timeout_salvage_failed",
                            job_id=job.job_id,
                            persona=job.persona,
                            error=str(exc),
                        )
                    if salvaged is not None:
                        logger.warning(
                            "worker job soft-timeout salvaged",
                            job_id=job.job_id,
                            persona=job.persona,
                            tool_count=tool_count,
                            salvaged=True,
                        )
                        return salvaged
                    logger.error(
                        "worker job timed out",
                        job_id=job.job_id,
                        persona=job.persona,
                        timeout_s=job_timeout,
                        soft_timeout_s=soft_timeout,
                        tool_count=tool_count,
                        salvaged=False,
                    )
                    self._metrics.record_worker_job_timeout(job.persona)
                    await self._run_worker_job.mark_job_timeout(job)
                    return RunResult(
                        job_id=job.job_id,
                        persona=job.persona,
                        success=False,
                        error="worker_job_timeout",
                    )
        finally:
            state = JobBudgetTracker.get(session_id)
            if state is not None:
                self._metrics.record_job_usage(
                    job.persona,
                    tokens=state.tokens_used,
                    cost_usd=state.cost_usd,
                )
            JobBudgetTracker.clear(session_id)
            clear_tool_execution_count(job.job_id)
            get_container().get_tool_chain_policy().clear(job.job_id)
            reset_correlation_id(cid_token)
            structlog.contextvars.unbind_contextvars("persona", "job_id", "correlation_id", "work_kind")

    async def process_next(self) -> RunResult | None:
        job = await self.queue.adequeue(timeout=get_container().settings.worker_dequeue_timeout_s)
        if job is None:
            return None
        return await self.run_job(job)
