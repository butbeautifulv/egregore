from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from cys_core.application.use_cases.run_worker_job import RunWorkerJob
from cys_core.application.workers.agent_executor import WorkerAgentExecutor
from cys_core.application.workers.context_builder import WorkerContextBuilder
from cys_core.application.workers.finding_publisher import WorkerFindingPublisher
from cys_core.application.workers.job_finalizer import WorkerJobFinalizer
from cys_core.application.workers.result_validator import WorkerResultValidator
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.sanitizer import InputSanitizer
from tests.application.port_fakes import fake_worker_tracing_port


def build_run_worker_job_for_tests(**overrides) -> RunWorkerJob:
    """Build RunWorkerJob with in-memory fakes for unit/integration tests."""
    bus = overrides.pop(
        "bus",
        SimpleNamespace(
            send_message=lambda *a, **k: {"signature": "sig-1"},
            receive_message=lambda *a, **k: None,
            record_agent_failure=lambda *a, **k: None,
        ),
    )
    transport = overrides.pop("transport", SimpleNamespace(publish_delivery=AsyncMock()))
    queue = overrides.pop("queue", SimpleNamespace(send_to_dlq=None))
    job_store = overrides.pop(
        "job_store",
        SimpleNamespace(
            upsert_running=lambda *a, **k: None,
            mark_completed=lambda *a, **k: None,
            mark_failed=lambda *a, **k: None,
        ),
    )
    registry = overrides.pop(
        "registry",
        SimpleNamespace(
            get=lambda _name: SimpleNamespace(
                schema_name="SocFinding",
                tools=[],
                skills=[],
                bus_recipients=[],
            )
        ),
    )
    sandbox = overrides.pop(
        "sandbox",
        SimpleNamespace(
            acreate=AsyncMock(return_value=SimpleNamespace(sandbox_id="sb-1")),
            adestroy=AsyncMock(),
        ),
    )
    runtime = overrides.pop("runtime", SimpleNamespace(arun=AsyncMock(return_value={"summary": "ok"})))
    engagement_store = overrides.pop("engagement_store", None)
    engagement_egress = overrides.pop("engagement_egress", None)
    memory_reader = overrides.pop("memory_reader", None)
    memory_writer = overrides.pop("memory_writer", None)
    agent_catalog = overrides.pop("agent_catalog", SimpleNamespace(get_agent=lambda name: None))

    context_builder = WorkerContextBuilder(
        engagement_store=engagement_store,
        memory_reader=memory_reader,
    )
    agent_executor = WorkerAgentExecutor(runtime=runtime)
    result_validator = WorkerResultValidator(
        schema_registry=SimpleNamespace(get=lambda name: object()),
        guardrails=OutputGuardrails(),
    )
    finding_publisher = WorkerFindingPublisher(
        bus=bus,
        transport=transport,
        memory_writer=memory_writer,
        engagement_store=engagement_store,
    )
    job_finalizer = WorkerJobFinalizer(
        job_store=job_store,
        queue=queue,
        bus=bus,
        agent_catalog=agent_catalog,
        engagement_store=engagement_store,
        engagement_egress=engagement_egress,
    )
    return RunWorkerJob(
        context_builder=context_builder,
        agent_executor=agent_executor,
        result_validator=result_validator,
        finding_publisher=finding_publisher,
        job_finalizer=job_finalizer,
        registry=registry,
        sandbox=sandbox,
        sanitizer=overrides.pop("sanitizer", InputSanitizer()),
        worker_tracing=overrides.pop("worker_tracing", fake_worker_tracing_port()),
        use_tool_gateway=overrides.pop("use_tool_gateway", False),
        resolve_mcp_tools=overrides.pop("resolve_mcp_tools", lambda *a, **k: []),
        resolve_legacy_tools=overrides.pop("resolve_legacy_tools", lambda *a, **k: []),
        make_load_skill_tool=overrides.pop("make_load_skill_tool", lambda *a, **k: None),
        **overrides,
    )
