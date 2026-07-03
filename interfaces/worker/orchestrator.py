from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from bootstrap.container import get_container
from bootstrap.settings import settings, get_settings
from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID, resolve_profile_id
from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.factory import get_input_sanitizer, get_output_guardrails
from cys_core.domain.workers.budgets import enrich_job_budget
from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.domain.workers.models import RunResult, WorkerJob
from cys_core.infrastructure.bus_transport import get_bus_transport
from cys_core.infrastructure.memory.factory import get_memory_read_service, get_memory_write_service
from cys_core.infrastructure.queue import get_job_queue
from cys_core.infrastructure.sandbox import get_sandbox_connector
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id
from cys_core.observability.worker_spans import observability_span, worker_job_span
from cys_core.registry.agents import AgentRegistry, get_agent_registry
from cys_core.registry.mcp_tools import mcp_tool_registry
from cys_core.registry.skills_tool import make_load_skill_tool
from cys_core.runtime.agent import AgentRuntime, get_runtime
from interfaces.gateways.tool.policy import clear_chain_state
from interfaces.control_plane.status_store import get_status_store

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


def _resolve_legacy_tools(tool_names: list[str]) -> list:
    from cys_core.registry.tools import tool_registry

    return tool_registry.resolve(tool_names)


class WorkerOrchestrator:
    """Dequeue → sandbox → agent run → bus publish → sandbox destroy."""

    def __init__(
        self,
        *,
        persona: str | None = None,
        runtime: AgentRuntime | None = None,
        bus: SecureAgentBus | None = None,
        registry: AgentRegistry | None = None,
    ) -> None:
        self.persona = persona
        self.runtime = runtime or get_runtime()
        self.registry = registry or get_agent_registry()
        self.bus = bus or build_agent_bus(self.registry, signing_key=settings.bus_signing_key_bytes)
        self.sandbox = get_sandbox_connector()
        self.queue = get_job_queue(persona=persona)
        self.transport = get_bus_transport()
        self.sanitizer = get_input_sanitizer()
        self.guardrails = get_output_guardrails()
        container = get_container()
        self.job_store = container.get_job_store()
        status_store = get_status_store()
        self._run_worker_job = RunWorkerJob(
            runtime=self.runtime,
            registry=self.registry,
            bus=self.bus,
            sandbox=self.sandbox,
            transport=self.transport,
            queue=self.queue,
            sanitizer=self.sanitizer,
            guardrails=self.guardrails,
            job_store=self.job_store,
            use_tool_gateway=settings.use_tool_gateway,
            resolve_mcp_tools=mcp_tool_registry.resolve,
            resolve_legacy_tools=_resolve_legacy_tools,
            make_load_skill_tool=make_load_skill_tool,
            memory_reader=get_memory_read_service(),
            memory_writer=get_memory_write_service(),
            investigation_store=container.get_investigation_state_store(),
            investigation_status_notifier=(
                status_store if hasattr(status_store, "record_investigation_update") else None
            ),
            record_sanitizer_block=metrics.record_sanitizer_block,
            record_memory_write=metrics.record_memory_write,
        )

    async def run_job(self, job: WorkerJob) -> RunResult:
        if job.depends_on_persona:
            investigation_id = job.correlation_id or job.event_id
            container = get_container()
            state = container.get_investigation_state_store().get(job.tenant_id, investigation_id)
            completed = state.completed_personas if state is not None else []
            if job.depends_on_persona not in completed:
                await self.queue.aenqueue(job.model_dump())
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
        from cys_core.infrastructure.catalog.hybrid_registry import get_agent_catalog

        catalog_entry = get_agent_catalog().get_agent(budgeted.persona)
        profile_id = resolve_profile_id(
            payload=budgeted.payload,
            catalog_entry=catalog_entry,
        )
        from cys_core.domain.workers.job_budget import configure_job_cost
        from cys_core.infrastructure.catalog.profile_policy import get_cost_per_1k_tokens

        configure_job_cost(get_cost_per_1k_tokens(profile_id), profile_id=profile_id)
        JobBudgetTracker.configure(
            session_id,
            max_tokens=budgeted.max_tokens,
            max_cost_usd=budgeted.max_cost_usd,
            max_tool_calls=budgeted.max_tool_calls,
            profile_id=profile_id,
        )
        try:
            with worker_job_span(
                persona=job.persona,
                job_id=job.job_id,
                investigation_id=investigation_id,
            ):
                with metrics.track_worker_job(job.persona) as job_state:
                    self._run_worker_job.sanitizer = self.sanitizer
                    self._run_worker_job.transport = self.transport
                    job_timeout = get_settings().worker_job_timeout
                    return await asyncio.wait_for(
                        self._run_worker_job.execute(job, budgeted, session_id, job_state),
                        timeout=job_timeout,
                    )
        except TimeoutError:
            logger.error(
                "worker job timed out",
                job_id=job.job_id,
                persona=job.persona,
                timeout_s=get_settings().worker_job_timeout,
            )
            self.job_store.mark_failed(job.job_id)
            self._run_worker_job._mark_persona_terminal(job)
            return RunResult(
                job_id=job.job_id,
                persona=job.persona,
                success=False,
                error="worker_job_timeout",
            )
        finally:
            state = JobBudgetTracker.get(session_id)
            if state is not None:
                metrics.record_job_usage(
                    job.persona,
                    tokens=state.tokens_used,
                    cost_usd=state.cost_usd,
                )
            JobBudgetTracker.clear(session_id)
            clear_chain_state(job.job_id)
            reset_correlation_id(cid_token)
            structlog.contextvars.unbind_contextvars("persona", "job_id", "correlation_id")

    async def process_next(self) -> RunResult | None:
        with observability_span("worker.dequeue", persona=self.persona or ""):
            raw = await self.queue.adequeue(timeout=2.0)
        if raw is None:
            return None
        job = WorkerJob.model_validate(raw)
        return await self.run_job(job)

    def _jobs_for_routing(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        sequential: bool = False,
    ) -> list[WorkerJob]:
        jobs: list[WorkerJob] = []
        previous_persona = ""
        for persona in personas:
            job_id = f"{persona}-{event_id}-{uuid.uuid4().hex[:8]}"
            jobs.append(
                WorkerJob(
                    job_id=job_id,
                    event_id=event_id,
                    persona=persona,
                    playbook_id=playbook_id,
                    payload=payload or {},
                    correlation_id=correlation_id or event_id,
                    tenant_id=tenant_id,
                    depends_on_persona=previous_persona if sequential else "",
                )
            )
            if sequential:
                previous_persona = persona
        return jobs

    def _persist_and_enqueue_jobs(self, jobs: list[WorkerJob]) -> list[str]:
        job_ids: list[str] = []
        for job in jobs:
            self.job_store.upsert_pending(
                job.job_id,
                job.persona,
                correlation_id=job.correlation_id,
                tenant_id=job.tenant_id,
                event_id=job.event_id,
            )
            self.queue.enqueue(job.model_dump())
            job_ids.append(job.job_id)
        return job_ids

    async def _apersist_and_enqueue_jobs(self, jobs: list[WorkerJob]) -> list[str]:
        job_ids: list[str] = []
        for job in jobs:
            self.job_store.upsert_pending(
                job.job_id,
                job.persona,
                correlation_id=job.correlation_id,
                tenant_id=job.tenant_id,
                event_id=job.event_id,
            )
            await self.queue.aenqueue(job.model_dump())
            job_ids.append(job.job_id)
        return job_ids

    def enqueue_from_routing_sync(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        sequential: bool = False,
    ) -> list[str]:
        jobs = self._jobs_for_routing(
            event_id,
            personas,
            playbook_id=playbook_id,
            payload=payload,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            sequential=sequential,
        )
        return self._persist_and_enqueue_jobs(jobs)

    async def enqueue_from_routing(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
        tenant_id: str = "default",
        sequential: bool = False,
    ) -> list[str]:
        jobs = self._jobs_for_routing(
            event_id,
            personas,
            playbook_id=playbook_id,
            payload=payload,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            sequential=sequential,
        )
        return await self._apersist_and_enqueue_jobs(jobs)
