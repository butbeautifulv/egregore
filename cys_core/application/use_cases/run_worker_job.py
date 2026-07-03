from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from cys_core.application.runtime_config import get_stage
from cys_core.application.ports.bus import AgentTransportConnector
from cys_core.application.ports.job_queue import JobQueueConnector
from cys_core.application.ports.memory import InvestigationStateStore
from cys_core.application.ports.sandbox import SandboxConnector
from cys_core.domain.catalog.profile_id import resolve_profile_id
from cys_core.domain.memory.services import MemoryReadService, MemoryWriteService
from cys_core.domain.security.agent_bus import SecureAgentBus
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.sanitizer import InputSanitizer
from cys_core.runtime.agent import _parse_json_text
from cys_core.domain.workers.exceptions import JobBudgetExceeded
from cys_core.domain.workers.models import RunResult, WorkerJob, WorkerJobStatus
from cys_core.observability.metrics import metrics
from cys_core.observability.worker_spans import observability_span


class InvestigationStatusNotifier(Protocol):
    def record_investigation_update(self, payload: dict[str, Any]) -> None: ...


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
        memory_reader: MemoryReadService | None = None,
        memory_writer: MemoryWriteService | None = None,
        investigation_store: InvestigationStateStore | None = None,
        investigation_status_notifier: InvestigationStatusNotifier | None = None,
        record_sanitizer_block: Callable[[str, str], None] | None = None,
        record_memory_write: Callable[[str, str], None] | None = None,
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
        self.memory_reader = memory_reader
        self.memory_writer = memory_writer
        self.investigation_store = investigation_store
        self.investigation_status_notifier = investigation_status_notifier
        self.record_sanitizer_block = record_sanitizer_block or (lambda _where, _mode: None)
        self.record_memory_write = record_memory_write or (lambda _tenant, _memory_type: None)

    def _mark_persona_terminal(self, job: WorkerJob) -> None:
        """Unblock sequential downstream jobs after success or failure."""
        if self.investigation_store is None:
            return
        investigation_id = job.correlation_id or job.event_id
        self.investigation_store.mark_persona_done(job.tenant_id, investigation_id, job.persona)
        self._notify_investigation_update(job)

    def _notify_investigation_update(self, job: WorkerJob) -> None:
        if self.investigation_status_notifier is None or self.investigation_store is None:
            return
        investigation_id = job.correlation_id or job.event_id
        state = self.investigation_store.get(job.tenant_id, investigation_id)
        if state is None:
            return
        self.investigation_status_notifier.record_investigation_update(
            {
                "investigation_id": investigation_id,
                "tenant_id": job.tenant_id,
                "status": state.status,
                "completed_personas": list(state.completed_personas),
                "persona": job.persona,
                "planner_status": state.planner_status,
            }
        )

    def _memory_investigation_id(self, job: WorkerJob) -> str:
        parent_key = job.payload.get("parent_correlation_key")
        if parent_key:
            return str(parent_key)
        return job.correlation_id or job.event_id

    def _investigation_context(self, job: WorkerJob) -> dict[str, Any]:
        investigation_id = self._memory_investigation_id(job)
        context: dict[str, Any] = {"investigation_id": investigation_id, "tenant_id": job.tenant_id}
        if self.investigation_store is not None:
            state = self.investigation_store.get(job.tenant_id, investigation_id)
            if state is not None:
                context["state"] = state.model_dump(mode="json")
        if self.memory_reader is not None:
            with observability_span(
                "worker.memory.load",
                tenant_id=job.tenant_id,
                investigation_id=investigation_id,
            ):
                entries = self.memory_reader.query_investigation(
                    job.tenant_id,
                    investigation_id,
                    limit=10,
                    requesting_tenant_id=job.tenant_id,
                )
            if entries:
                metrics.record_memory_read(job.tenant_id, entries_loaded=len(entries))
                context["prior_findings"] = [
                    {
                        "agent": entry.source_agent,
                        "type": entry.memory_type,
                        "content": entry.content,
                        "job_id": entry.source_job_id,
                    }
                    for entry in entries
                ]
        return context

    def _job_input(self, job: WorkerJob) -> str:
        return json.dumps(
            {
                "event_id": job.event_id,
                "playbook_id": job.playbook_id,
                "payload": job.payload,
                "sandbox_id": job.sandbox_id,
                "feedback": job.feedback,
                "investigation_context": self._investigation_context(job),
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
        investigation_id = self._memory_investigation_id(job)
        try:
            with observability_span("worker.sandbox.create", persona=job.persona, job_id=job.job_id):
                creds = await self.sandbox.acreate(run_id, job.persona)
            job.sandbox_id = creds.sandbox_id
            job.status = WorkerJobStatus.RUNNING
            self.job_store.upsert_running(
                job.job_id,
                session_id,
                job.persona,
                correlation_id=job.correlation_id,
                tenant_id=job.tenant_id,
                event_id=job.event_id,
            )

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

            with observability_span("worker.agent.run", persona=job.persona, job_id=job.job_id):
                result = await self.runtime.arun(
                    job.persona,
                    sanitized,
                    session_id=session_id,
                    sandbox_tools=sandbox_tools or None,
                    job_id=job.job_id,
                    event_id=job.event_id,
                    correlation_id=job.correlation_id,
                    tenant_id=job.tenant_id,
                    investigation_id=investigation_id,
                    sandbox_id=creds.sandbox_id,
                )

            if isinstance(result, dict) and "raw_response" in result and "error" not in result:
                parsed = _parse_json_text(str(result["raw_response"]))
                if parsed:
                    result = parsed

            result = await self._maybe_self_refine(job, sanitized, result)

            schema = self._schema_registry_get(defn.schema_name or "")
            if isinstance(result, dict) and "error" not in result:
                if isinstance(result.get("reasoning_steps"), list):
                    result["sgr_metadata"] = {
                        "reasoning_steps": result.get("reasoning_steps"),
                        "plan_status": result.get("plan_status", ""),
                        "enough_data": result.get("enough_data", False),
                    }
            if schema and isinstance(result, dict) and "error" not in result:
                try:
                    validated = self.guardrails.validate_schema(result, schema)
                    result = validated.model_dump()
                except SecurityViolation:
                    if get_stage() == "dev":
                        pass
                    else:
                        raise

            finding_payload = {
                "agent": job.persona,
                "event_id": job.event_id,
                "correlation_id": investigation_id,
                "tenant_id": job.tenant_id,
                "job_id": job.job_id,
                "data": result,
                "sandbox_id": creds.sandbox_id,
            }
            recipients = list(dict.fromkeys([*(getattr(defn, "bus_recipients", None) or []), "critic"]))
            for recipient in recipients:
                envelope = self.bus.send_message(job.persona, recipient, "finding", finding_payload)
                self.bus.receive_message(recipient, envelope)
                await self.transport.publish(recipient, envelope)

            if self.memory_writer is not None and isinstance(result, dict):
                entry = self.memory_writer.append_pending_finding(
                    tenant_id=job.tenant_id,
                    investigation_id=investigation_id,
                    source_agent=job.persona,
                    source_job_id=job.job_id,
                    finding=result,
                )
                if entry is not None:
                    self.record_memory_write(job.tenant_id, entry.memory_type)

            if self.investigation_store is not None and isinstance(result, dict) and "error" not in result:
                self.investigation_store.append_finding(
                    job.tenant_id,
                    investigation_id,
                    {
                        "persona": job.persona,
                        "job_id": job.job_id,
                        "finding": result,
                    },
                )

            self._mark_persona_terminal(job)

            job.status = WorkerJobStatus.COMPLETED
            self.job_store.mark_completed(job.job_id)
            try:
                from bootstrap.settings import get_settings
                from cys_core.application.persona_quality_hooks import record_job_completed

                cost = float(job.payload.get("estimated_cost_usd", 0.0))
                from cys_core.infrastructure.catalog.hybrid_registry import get_agent_catalog

                catalog_entry = get_agent_catalog().get_agent(job.persona)
                profile_id = resolve_profile_id(payload=job.payload, catalog_entry=catalog_entry)
                record_job_completed(job.persona, success=True, cost_usd=cost, profile_id=profile_id)
            except Exception:
                pass
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
            self._mark_persona_terminal(job)
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
        except SecurityViolation as exc:
            job_state["status"] = "error"
            self.record_sanitizer_block("worker", "hard")
            job.status = WorkerJobStatus.FAILED
            self.job_store.mark_failed(job.job_id)
            self._mark_persona_terminal(job)
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
        except Exception as exc:
            job_state["status"] = "error"
            self.bus.record_agent_failure(job.persona)
            try:
                from cys_core.application.persona_quality_hooks import record_bus_failure, record_job_completed

                from cys_core.infrastructure.catalog.hybrid_registry import get_agent_catalog

                catalog_entry = get_agent_catalog().get_agent(job.persona)
                profile_id = resolve_profile_id(payload=job.payload, catalog_entry=catalog_entry)
                record_bus_failure(job.persona, profile_id=profile_id)
                record_job_completed(job.persona, success=False, profile_id=profile_id)
            except Exception:
                pass
            job.status = WorkerJobStatus.FAILED
            self.job_store.mark_failed(job.job_id)
            self._mark_persona_terminal(job)
            send_dlq = getattr(self.queue, "send_to_dlq", None)
            if send_dlq is not None:
                await send_dlq(job.model_dump(), str(exc))
            return RunResult(job_id=job.job_id, persona=job.persona, success=False, error=str(exc))
        finally:
            with observability_span("worker.sandbox.destroy", persona=job.persona, job_id=job.job_id):
                await self.sandbox.adestroy(run_id)

    async def _maybe_self_refine(self, job: WorkerJob, sanitized: str, result: dict[str, Any]) -> dict[str, Any]:
        from cys_core.application.runtime_config import get_self_refine_max

        max_rounds = get_self_refine_max()
        if max_rounds <= 0 or not isinstance(result, dict) or "error" in result:
            return result
        draft = json.dumps(result, ensure_ascii=False)
        rounds_done = 0
        for round_idx in range(max_rounds):
            rounds_done = round_idx + 1
            critique_prompt = (
                f"Critique this worker output for persona {job.persona}. "
                f"Input:\n{sanitized[:2000]}\nOutput:\n{draft[:4000]}\n"
                "Reply JSON: {\"revise\":true|false,\"notes\":\"...\"}"
            )
            revised = await self.runtime.arun(
                job.persona,
                critique_prompt,
                session_id=f"refine:{job.job_id}:{round_idx}",
                tenant_id=job.tenant_id,
                investigation_id=job.correlation_id or job.event_id,
            )
            if not isinstance(revised, dict):
                break
            notes = str(revised.get("notes", revised.get("raw_response", "")))
            if not notes:
                break
            revise_prompt = f"Revise your prior output addressing: {notes}\nPrior:\n{draft[:4000]}"
            updated = await self.runtime.arun(
                job.persona,
                revise_prompt,
                session_id=f"refine:{job.job_id}:{round_idx}:write",
                tenant_id=job.tenant_id,
                investigation_id=job.correlation_id or job.event_id,
            )
            if isinstance(updated, dict) and "error" not in updated:
                result = updated
                draft = json.dumps(result, ensure_ascii=False)
            else:
                break
        result["self_refine_rounds"] = rounds_done
        return result

    def _schema_registry_get(self, name: str) -> Any:
        from cys_core.registry.schemas import schema_registry

        return schema_registry.get(name)
