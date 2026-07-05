from __future__ import annotations

import asyncio
from typing import Any

import structlog

from bootstrap.container import get_container
from bootstrap.settings import settings
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID, resolve_profile_id
from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.factory import get_input_sanitizer
from cys_core.infrastructure.policy.budget_adapter import enrich_job_budget
from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.domain.workers.models import RunResult, WorkerJob
from cys_core.infrastructure.bus_transport import get_bus_transport
from cys_core.infrastructure.sandbox import get_sandbox_connector
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id
from cys_core.registry.agents import AgentRegistry, get_agent_registry
from cys_core.runtime.agent import AgentRuntime, get_runtime

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


class WorkerOrchestrator:
    """Dequeue → budget → worker pipeline execution."""

    def __init__(
        self,
        *,
        persona: str | None = None,
        runtime: AgentRuntime | None = None,
        bus: SecureAgentBus | None = None,
        registry: AgentRegistry | None = None,
        transport: Any = None,
        sanitizer: Any = None,
    ) -> None:
        self.persona = persona
        self.runtime = runtime or get_runtime()
        self.registry = registry or get_agent_registry()
        self.bus = bus or build_agent_bus(self.registry, signing_key=settings.bus_signing_key_bytes)
        container = get_container()
        self.sandbox = get_sandbox_connector()
        self.queue = container.get_job_queue(persona=persona)
        self.transport = transport or get_bus_transport()
        self.sanitizer = sanitizer or get_input_sanitizer()
        self._metrics = container.get_metrics_port()
        self._tracing = container.get_worker_tracing_port()
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

    async def run_job(self, job: WorkerJob) -> RunResult:
        container = get_container()
        if job.depends_on_persona:
            investigation_id = job.correlation_id or job.event_id
            state = container.get_engagement_state_store().get(job.tenant_id, investigation_id)
            completed = state.completed_personas if state is not None else []
            if job.depends_on_persona not in completed:
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
        investigation_id = job.correlation_id or job.event_id
        cid_token = bind_correlation_id(investigation_id)
        structlog.contextvars.bind_contextvars(
            persona=job.persona,
            job_id=job.job_id,
            correlation_id=investigation_id,
        )
        catalog_entry = container.get_agent_catalog().get_agent(budgeted.persona)
        profile_id = resolve_profile_id(
            payload=budgeted.payload,
            catalog_entry=catalog_entry,
        )
        from cys_core.domain.workers.job_budget import configure_job_cost

        cost_rate = container.get_profile_policy_port().get_cost_per_1k_tokens(profile_id)
        if cost_rate <= 0:
            cost_rate = container.settings.job_cost_per_1k_tokens_usd
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
                job_timeout = container.settings.worker_job_timeout
                return await asyncio.wait_for(
                    self._run_worker_job.execute(job, budgeted, session_id, job_state),
                    timeout=job_timeout,
                )
        except TimeoutError:
            logger.error(
                "worker job timed out",
                job_id=job.job_id,
                persona=job.persona,
                timeout_s=container.settings.worker_job_timeout,
            )
            self.job_store.mark_failed(job.job_id)
            self._run_worker_job._mark_persona_completed(job)
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
            get_container().get_tool_chain_policy().clear(job.job_id)
            reset_correlation_id(cid_token)
            structlog.contextvars.unbind_contextvars("persona", "job_id", "correlation_id")

    async def process_next(self) -> RunResult | None:
        with self._tracing.span("worker.dequeue", persona=self.persona or ""):
            job = await self.queue.adequeue(timeout=2.0)
        if job is None:
            return None
        return await self.run_job(job)
