from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from cys_core.application.ports.agent_runner import AgentRunner
from cys_core.application.ports.bus import AgentTransportConnector
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.sandbox import SandboxConnector
from cys_core.domain.security.agent_bus import SecureAgentBus
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.sanitizer import InputSanitizer
from cys_core.domain.workers.exceptions import JobBudgetExceeded
from cys_core.domain.workers.models import RunResult, WorkerJob, WorkerJobStatus


class AgentRegistryPort(Protocol):
    def get(self, name: str) -> Any: ...


class SchemaRegistryPort(Protocol):
    def get(self, name: str) -> Any: ...


class JobStorePort(Protocol):
    def upsert_running(self, job_id: str, session_id: str, persona: str) -> None: ...
    def mark_completed(self, job_id: str) -> None: ...
    def mark_failed(self, job_id: str) -> None: ...


class RunWorkerJob:
    """Execute one worker job: sandbox → agent → bus publish."""

    def __init__(
        self,
        *,
        runtime: AgentRunner,
        registry: AgentRegistryPort,
        bus: SecureAgentBus,
        sandbox: SandboxConnector,
        transport: AgentTransportConnector,
        queue: JobQueueConnector,
        sanitizer: InputSanitizer,
        guardrails: OutputGuardrails,
        job_store: JobStorePort,
        use_tool_gateway: bool,
        resolve_mcp_tools: Any,
        resolve_legacy_tools: Any,
        make_load_skill_tool: Any,
        record_sanitizer_block: Callable[[str, str], None] | None = None,
    ) -> None:
        self.runtime = runtime
        self.registry = registry
        self.bus = bus
        self.sandbox = sandbox
        self.transport = transport
        self.queue = queue
        self.sanitizer = sanitizer
        self.guardrails = guardrails
        self.job_store = job_store
        self.use_tool_gateway = use_tool_gateway
        self.resolve_mcp_tools = resolve_mcp_tools
        self.resolve_legacy_tools = resolve_legacy_tools
        self.make_load_skill_tool = make_load_skill_tool
        self.record_sanitizer_block = record_sanitizer_block or (lambda _where, _mode: None)

    def _job_input(self, job: WorkerJob) -> str:
        return json.dumps(
            {
                "event_id": job.event_id,
                "playbook_id": job.playbook_id,
                "payload": job.payload,
                "sandbox_id": job.sandbox_id,
                "feedback": job.feedback,
            },
            ensure_ascii=False,
        )

    async def execute(
        self,
        job: WorkerJob,
        budgeted: WorkerJob,
        session_id: str,
        job_state: dict[str, str],
    ) -> RunResult:
        run_id = job.job_id
        try:
            creds = await self.sandbox.acreate(run_id, job.persona)
            job.sandbox_id = creds.sandbox_id
            job.status = WorkerJobStatus.RUNNING
            self.job_store.upsert_running(job.job_id, session_id, job.persona)

            raw_input = self._job_input(job)
            sanitized = self.sanitizer.sanitize(raw_input, source="external")
            defn = self.registry.get(job.persona)
            sandbox_tools: list = []
            if self.use_tool_gateway:
                sandbox_tools.extend(
                    self.resolve_mcp_tools(
                        defn.tools,
                        creds.sandbox_id,
                        persona=job.persona,
                        job_id=job.job_id,
                        correlation_id=job.correlation_id,
                    )
                )
            else:
                sandbox_tools.extend(self.resolve_legacy_tools(defn.tools))
            if defn.skills:
                sandbox_tools.append(self.make_load_skill_tool(defn.skills, persona=job.persona, job_id=job.job_id))

            result = await self.runtime.arun(
                job.persona,
                sanitized,
                session_id=session_id,
                sandbox_tools=sandbox_tools or None,
                job_id=job.job_id,
                event_id=job.event_id,
                correlation_id=job.correlation_id,
                sandbox_id=creds.sandbox_id,
            )

            schema = self._schema_registry_get(defn.schema_name or "")
            if schema and "error" not in result:
                validated = self.guardrails.validate_schema(result, schema)
                result = validated.model_dump()

            envelope = self.bus.send_message(
                job.persona,
                "critic",
                "finding",
                {"agent": job.persona, "event_id": job.event_id, "data": result, "sandbox_id": creds.sandbox_id},
            )
            self.bus.receive_message("critic", envelope)
            await self.transport.publish("critic", envelope)
            await self.transport.publish("coordinator", envelope)

            job.status = WorkerJobStatus.COMPLETED
            self.job_store.mark_completed(job.job_id)
            return RunResult(
                job_id=job.job_id,
                persona=job.persona,
                success=True,
                finding=result,
                sandbox_id=creds.sandbox_id,
            )
        except JobBudgetExceeded as exc:
            job_state["status"] = "error"
            job.status = WorkerJobStatus.FAILED
            self.job_store.mark_failed(job.job_id)
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
        except SecurityViolation as exc:
            job_state["status"] = "error"
            self.record_sanitizer_block("worker", "hard")
            job.status = WorkerJobStatus.FAILED
            self.job_store.mark_failed(job.job_id)
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
        except Exception as exc:
            job_state["status"] = "error"
            self.bus.record_agent_failure(job.persona)
            job.status = WorkerJobStatus.FAILED
            self.job_store.mark_failed(job.job_id)
            send_dlq = getattr(self.queue, "send_to_dlq", None)
            if send_dlq is not None:
                await send_dlq(job.model_dump(), str(exc))
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
        finally:
            await self.sandbox.adestroy(run_id)

    def _schema_registry_get(self, name: str) -> Any:
        from cys_core.registry.schemas import schema_registry

        return schema_registry.get(name)
