from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from cys_core.application.use_cases.enqueue_next_planned_persona import EnqueueNextPlannedPersona
from cys_core.application.use_cases.enqueue_synthesis_job import EnqueueSynthesisJob
from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.application.workers.agent_executor import WorkerAgentExecutor
from cys_core.application.workers.context_builder import WorkerContextBuilder
from cys_core.application.workers.finding_publisher import WorkerFindingPublisher
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.application.runtime_config import get_self_refine_max, get_use_run_kernel
from cys_core.domain.security.factory import get_output_guardrails


@dataclass(frozen=True)
class WorkerPipelineDeps:
    engagement_store: Any
    memory_reader: Any
    memory_writer: Any
    metrics: Any
    runtime: Any
    schema_registry: Any
    bus: Any
    transport: Any
    queue: Any
    job_store: Any
    agent_catalog: Any
    engagement_egress: Any
    bus_guard: Any
    agent_registry: Any
    sandbox: Any
    sanitizer: Any
    worker_tracing: Any
    use_tool_gateway: bool
    dev_schema_bypass: bool
    resolve_mcp_tools: Callable[..., Any]
    resolve_legacy_tools: Callable[[list[str]], Any]
    make_load_skill_tool: Callable[..., Any]


def build_worker_pipeline(deps: WorkerPipelineDeps) -> RunWorkerJob:
    context_builder = WorkerContextBuilder(
        engagement_store=deps.engagement_store,
        memory_reader=deps.memory_reader,
        record_memory_read=lambda tenant, count: deps.metrics.record_memory_read(tenant, entries_loaded=count),
    )
    agent_executor = WorkerAgentExecutor(
        runtime=deps.runtime,
        use_run_kernel=get_use_run_kernel(),
        self_refine_max=get_self_refine_max(),
    )
    result_validator = WorkerResultValidator(
        schema_registry=deps.schema_registry,
        guardrails=get_output_guardrails(),
        dev_schema_bypass=deps.dev_schema_bypass,
    )
    finding_publisher = WorkerFindingPublisher(
        bus=deps.bus,
        transport=deps.transport,
        memory_writer=deps.memory_writer,
        engagement_store=deps.engagement_store,
        engagement_egress=deps.engagement_egress,
        bus_guard=deps.bus_guard,
        record_memory_write=deps.metrics.record_memory_write,
    )
    job_finalizer = WorkerJobFinalizer(
        job_store=deps.job_store,
        queue=deps.queue,
        bus=deps.bus,
        agent_catalog=deps.agent_catalog,
        engagement_store=deps.engagement_store,
        engagement_egress=deps.engagement_egress,
        enqueue_next_planned_persona=EnqueueNextPlannedPersona(
            engagement_store=deps.engagement_store,
            queue=deps.queue,
            engagement_egress=deps.engagement_egress,
        ),
        enqueue_synthesis_job=EnqueueSynthesisJob(
            engagement_store=deps.engagement_store,
            queue=deps.queue,
            engagement_egress=deps.engagement_egress,
        ),
        record_sanitizer_block=deps.metrics.record_sanitizer_block,
    )
    return RunWorkerJob(
        context_builder=context_builder,
        agent_executor=agent_executor,
        result_validator=result_validator,
        finding_publisher=finding_publisher,
        job_finalizer=job_finalizer,
        registry=deps.agent_registry,
        sandbox=deps.sandbox,
        sanitizer=deps.sanitizer,
        worker_tracing=deps.worker_tracing,
        use_tool_gateway=deps.use_tool_gateway,
        resolve_mcp_tools=deps.resolve_mcp_tools,
        resolve_legacy_tools=deps.resolve_legacy_tools,
        make_load_skill_tool=deps.make_load_skill_tool,
    )
