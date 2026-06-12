from __future__ import annotations

import uuid
from typing import Any

from bootstrap.settings import settings
from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.domain.security.agent_bus import AgentTrustLevel, SecureAgentBus
from cys_core.domain.security.factory import get_input_sanitizer, get_output_guardrails
from cys_core.domain.workers.budgets import enrich_job_budget
from cys_core.domain.workers.job_budget import JobBudgetTracker
from cys_core.domain.workers.models import RunResult, WorkerJob
from cys_core.infrastructure.bus_transport import get_bus_transport
from cys_core.infrastructure.queue import get_job_queue
from cys_core.infrastructure.sandbox import get_sandbox_connector
from cys_core.observability.metrics import metrics
from cys_core.observability.tracing import bind_correlation_id, reset_correlation_id
from cys_core.registry.agents import AgentRegistry, get_agent_registry
from cys_core.registry.mcp_tools import mcp_tool_registry
from cys_core.registry.skills_tool import make_load_skill_tool
from cys_core.runtime.agent import AgentRuntime, get_runtime
from interfaces.control_plane.job_store import get_job_store
from interfaces.gateways.tool.policy import clear_chain_state

_TRUST_MAP = {
    "untrusted": AgentTrustLevel.UNTRUSTED,
    "internal": AgentTrustLevel.INTERNAL,
    "privileged": AgentTrustLevel.PRIVILEGED,
    "system": AgentTrustLevel.SYSTEM,
}


def build_agent_bus(registry: AgentRegistry | None = None, signing_key: bytes = b"cys-agi-bus-key") -> SecureAgentBus:
    reg = registry or get_agent_registry()
    bus = SecureAgentBus(signing_key=signing_key)
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
        self.bus = bus or build_agent_bus(self.registry)
        self.sandbox = get_sandbox_connector()
        self.queue = get_job_queue(persona=persona)
        self.transport = get_bus_transport()
        self.sanitizer = get_input_sanitizer()
        self.guardrails = get_output_guardrails()
        self._run_worker_job = RunWorkerJob(
            runtime=self.runtime,
            registry=self.registry,
            bus=self.bus,
            sandbox=self.sandbox,
            transport=self.transport,
            queue=self.queue,
            sanitizer=self.sanitizer,
            guardrails=self.guardrails,
            job_store=get_job_store(),
            use_tool_gateway=settings.use_tool_gateway,
            resolve_mcp_tools=mcp_tool_registry.resolve,
            resolve_legacy_tools=_resolve_legacy_tools,
            make_load_skill_tool=make_load_skill_tool,
            record_sanitizer_block=metrics.record_sanitizer_block,
        )

    async def run_job(self, job: WorkerJob) -> RunResult:
        budgeted = enrich_job_budget(job)
        run_id = job.job_id
        session_id = f"worker:{job.persona}:{run_id}"
        cid_token = bind_correlation_id(job.correlation_id or job.event_id)
        JobBudgetTracker.configure(
            session_id,
            max_tokens=budgeted.max_tokens,
            max_cost_usd=budgeted.max_cost_usd,
            max_tool_calls=budgeted.max_tool_calls,
        )
        try:
            with metrics.track_worker_job(job.persona) as job_state:
                self._run_worker_job.sanitizer = self.sanitizer
                self._run_worker_job.transport = self.transport
                return await self._run_worker_job.execute(job, budgeted, session_id, job_state)
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

    async def process_next(self) -> RunResult | None:
        raw = await self.queue.adequeue(timeout=0.0)
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
    ) -> list[WorkerJob]:
        jobs: list[WorkerJob] = []
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
                )
            )
        return jobs

    def enqueue_from_routing_sync(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
    ) -> list[str]:
        job_ids: list[str] = []
        for job in self._jobs_for_routing(
            event_id,
            personas,
            playbook_id=playbook_id,
            payload=payload,
            correlation_id=correlation_id,
        ):
            self.queue.enqueue(job.model_dump())
            job_ids.append(job.job_id)
        return job_ids

    async def enqueue_from_routing(
        self,
        event_id: str,
        personas: list[str],
        *,
        playbook_id: str = "",
        payload: dict[str, Any] | None = None,
        correlation_id: str = "",
    ) -> list[str]:
        job_ids: list[str] = []
        for job in self._jobs_for_routing(
            event_id,
            personas,
            playbook_id=playbook_id,
            payload=payload,
            correlation_id=correlation_id,
        ):
            await self.queue.aenqueue(job.model_dump())
            job_ids.append(job.job_id)
        return job_ids
