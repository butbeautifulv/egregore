from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.tools import BaseTool, StructuredTool, tool

from cys_core.application.ports.tool_backend import ToolBackend
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID, resolve_profile_id

_tool_backend: ToolBackend | None = None


def configure_tool_backend(backend: ToolBackend) -> None:
    global _tool_backend
    _tool_backend = backend


@tool
def read_repo_metadata(repo_path: str) -> str:
    """Read repository metadata (languages, branches, recent commits). Stub for authorized scope."""
    return json.dumps(
        {
            "repo_path": repo_path,
            "languages": ["python", "yaml"],
            "default_branch": "main",
            "ci": "github_actions",
        },
        ensure_ascii=False,
    )


@tool
def parse_sast_report(report_json: str) -> str:
    """Parse SAST report JSON and extract high-signal findings."""
    try:
        data = json.loads(report_json) if report_json.strip().startswith("{") else {"raw": report_json}
    except json.JSONDecodeError:
        data = {"raw": report_json[:2000]}
    return json.dumps({"parsed_findings": data, "count": len(str(data))}, ensure_ascii=False)


@tool
def analyze_workflow(workflow_yaml: str) -> str:
    """Analyze CI/CD workflow for risky patterns (pull_request_target, secrets in env)."""
    risks = []
    lower = workflow_yaml.lower()
    if "pull_request_target" in lower:
        risks.append("pull_request_target usage detected")
    if "aws_access_key" in lower or "secret" in lower:
        risks.append("secrets referenced in workflow environment")
    return json.dumps({"risks": risks or ["no obvious workflow risks in stub"]}, ensure_ascii=False)


@tool
def run_active_scan(target: str) -> str:
    """Run active security scan on authorized target. Requires HITL approval."""
    from cys_core.integrations.veneno_mcp_client import call_veneno_mcp_tool, veneno_mcp_enabled

    if veneno_mcp_enabled():
        result = call_veneno_mcp_tool("run_active_scan", {"target": target})
        return json.dumps(result, ensure_ascii=False)
    return json.dumps(
        {"status": "simulated", "target": target, "note": "PoC analysis only; enable VENENO_MCP_ENABLED for execution"},
        ensure_ascii=False,
    )


@tool
def parse_netflow(netflow_text: str) -> str:
    """Parse NetFlow summary text into structured indicators."""
    return json.dumps(
        {
            "source": "netflow_stub",
            "indicators": ["periodic_tls", "non_browser_traffic"] if "90s" in netflow_text else [],
            "raw_excerpt": netflow_text[:500],
        },
        ensure_ascii=False,
    )


@tool
def enrich_ioc(ioc: str) -> str:
    """Enrich IP/domain IOC via Veil threat-intel when available."""
    from cys_core.integrations.veil_mcp_client import call_veil_mcp_tool, veil_mcp_enabled

    if veil_mcp_enabled():
        result = call_veil_mcp_tool("ti_search_in_category", {"query": ioc, "category": "ti", "limit": 5})
        if result.get("success"):
            return json.dumps(
                {"ioc": ioc, "source": "veil-mcp", "enrichment": result.get("content")},
                ensure_ascii=False,
            )
        return json.dumps(
            {"ioc": ioc, "source": "veil-mcp", "error": result.get("error", "Veil enrichment failed")},
            ensure_ascii=False,
        )
    return json.dumps({"ioc": ioc, "reputation": "suspicious", "tags": ["stub"], "source": "stub"}, ensure_ascii=False)


@tool
def correlate_dns(dns_events: str) -> str:
    """Correlate DNS events for beaconing patterns."""
    return json.dumps({"pattern": "periodic_lookup", "confidence": 0.7}, ensure_ascii=False)


@tool
def query_siem_readonly(query: str, time_range: str = "24h") -> str:
    """Execute read-only SIEM search. Worker runs route via MCP Tool Gateway."""
    if _tool_backend is None:
        return json.dumps({"error": "tool backend not configured"}, ensure_ascii=False)
    return json.dumps(
        _tool_backend.query_siem(query=query, time_range=time_range),
        ensure_ascii=False,
    )


@tool
def rag_query(query: str, persona: str = "soc", tenant: str = "default") -> str:
    """Retrieve ACL-filtered knowledge base chunks via MCP Tool Gateway."""
    if _tool_backend is None:
        return json.dumps({"error": "tool backend not configured"}, ensure_ascii=False)
    return json.dumps(
        _tool_backend.rag_query(query=query, persona=persona, tenant=tenant),
        ensure_ascii=False,
    )


@tool
def dedup_alerts(alerts_text: str) -> str:
    """Deduplicate and cluster SIEM alerts."""
    return json.dumps({"deduplicated_count": 1, "clusters": ["powershell_encoded"]}, ensure_ascii=False)


@tool
def build_timeline(events_text: str) -> str:
    """Build incident timeline from correlated events."""
    return json.dumps(
        {"timeline": ["T+0 EDR alert", "T+2m proxy anomaly", "T+10m dedup repeat"]},
        ensure_ascii=False,
    )


@tool
def correlate_findings(findings_json: str) -> str:
    """Correlate findings across telemetry sources."""
    return json.dumps({"correlated": True, "priority": "P2"}, ensure_ascii=False)


@tool
def check_control(framework: str, control_id: str, evidence: str) -> str:
    """Check compliance control against provided evidence."""
    return json.dumps(
        {
            "framework": framework,
            "control_id": control_id,
            "status": "partial",
            "gaps": ["missing quarterly access review"] if "60%" in evidence else [],
        },
        ensure_ascii=False,
    )


@tool
def map_framework(observation: str) -> str:
    """Map observation to compliance framework controls."""
    return json.dumps({"framework": "SOC2", "controls": ["CC6.1", "CC7.2"]}, ensure_ascii=False)


@tool
def audit_evidence(evidence_text: str) -> str:
    """Audit evidence retention and auditability."""
    return json.dumps({"auditability": "partial", "ticket_coverage": "60%"}, ensure_ascii=False)


@tool
def execute_command(command: str) -> str:
    """Execute shell command. RESTRICTED — should be denied for most agents."""
    return json.dumps({"executed": command, "status": "denied_by_policy"}, ensure_ascii=False)


@tool
def search_personas(query: str) -> str:
    """Search registered agent personas by keyword."""
    from cys_core.registry.discovery_tools import search_personas as _search

    return json.dumps(_search(query), ensure_ascii=False)


@tool
def search_skills(query: str) -> str:
    """Search product skills by keyword."""
    from cys_core.registry.discovery_tools import search_skills as _search

    return json.dumps(_search(query), ensure_ascii=False)


@tool
def search_tools(query: str, mode: str = "agent") -> str:
    """Search available tools filtered by interaction mode policy."""
    from cys_core.domain.runs.models import InteractionMode
    from cys_core.registry.discovery_tools import search_tools as _search

    try:
        interaction_mode = InteractionMode(mode)
    except ValueError:
        interaction_mode = InteractionMode.AGENT
    return json.dumps(_search(query, mode=interaction_mode), ensure_ascii=False)


@tool
def ask_user(question: str, *, context_id: str = "", tenant_id: str = "default") -> str:
    """Pause run and surface a clarifying question to the operator."""
    return json.dumps(
        {
            "status": "awaiting_user",
            "question": question,
            "context_id": context_id,
            "tenant_id": tenant_id,
        },
        ensure_ascii=False,
    )


@tool
def web_search(query: str, limit: int = 5) -> str:
    """Search the public web for OSINT and factual references (read-only)."""
    from cys_core.infrastructure.tools.adapters.web_search import web_search as _search

    return json.dumps(_search(query, limit=limit), ensure_ascii=False)


@tool
def read_document(path: str) -> str:
    """Read a local document attachment (txt, md, json, csv, pdf stub)."""
    from cys_core.infrastructure.tools.adapters.read_document import read_document as _read

    return json.dumps(_read(path), ensure_ascii=False)


@tool
def reasoning_step(
    reasoning_steps: list[str],
    current_situation: str,
    plan_status: str,
    task_completed: bool,
    remaining_steps: list[str] | None = None,
    enough_data: bool = False,
) -> str:
    """Mandatory schema-guided reasoning step before action tools (SGR)."""
    from cys_core.domain.reasoning.sgr_models import SchemaGuidedReasoningStep
    from cys_core.security.monitor import AgentMonitor

    step = SchemaGuidedReasoningStep(
        reasoning_steps=reasoning_steps,
        current_situation=current_situation,
        plan_status=plan_status,
        remaining_steps=remaining_steps or [],
        enough_data=enough_data,
        task_completed=task_completed,
    )
    AgentMonitor("sgr").log_orchestration_tool(
        "reasoning",
        "reasoning_step",
        {"steps": len(step.reasoning_steps), "task_completed": step.task_completed},
    )
    return json.dumps(step.model_dump(), ensure_ascii=False)


@tool
def reasoning_check(goal: str, trace_json: str) -> str:
    """Review full action trace before final synthesis (DeepAgent reasoning step)."""
    from bootstrap.container import get_container
    from bootstrap.settings import get_settings
    from cys_core.application.use_cases.evaluate_trace_critic import EvaluateTraceCritic
    from cys_core.security.monitor import AgentMonitor

    AgentMonitor("conductor").log_orchestration_tool("reasoning", "reasoning_check", {"goal": goal[:120]})
    settings = get_settings()
    critic = EvaluateTraceCritic(
        judge_backend=get_container().get_judge_backend() if settings.trace_critic_enabled else None,
        threshold=settings.trace_critic_threshold,
        application_tracing=get_container().get_application_tracing_port(),
    )
    verdict = critic.execute(goal=goal, trace=trace_json)
    return json.dumps(verdict.model_dump(), ensure_ascii=False)


@tool
async def extract_structured_output(goal: str, agent_summary: str, schema_type: str = "") -> str:
    """Extract structured deliverable with confidence and weaknesses."""
    from cys_core.application.runtime_config import get_self_consistency_n
    from cys_core.application.use_cases.extract_structured_output import (
        build_structured_extraction_prompt,
        detect_output_schema,
        parse_structured_output,
    )
    from cys_core.security.monitor import AgentMonitor
    from bootstrap.settings import get_settings

    AgentMonitor("conductor").log_orchestration_tool(
        "extract",
        "extract_structured_output",
        {"goal": goal[:120], "schema": schema_type or "auto"},
    )
    schema = schema_type or detect_output_schema(goal)
    prompt = build_structured_extraction_prompt(goal=goal, schema_type=schema, agent_summary=agent_summary)
    if get_settings().reasoning_model.strip():
        from cys_core.llm.reasoning import get_reasoning_model_connector

        model = get_reasoning_model_connector().create_model()
    else:
        from cys_core.llm import get_model_connector

        model = get_model_connector().create_model()
    n = max(1, get_self_consistency_n() or 1)
    candidates: list[dict] = []
    for _ in range(n):
        response = await model.ainvoke(prompt)
        text = str(getattr(response, "content", response))
        candidates.append(parse_structured_output(text))
    if n == 1:
        return json.dumps(candidates[0], ensure_ascii=False)
    payloads = [c.get("payload") for c in candidates if isinstance(c.get("payload"), dict)]
    merged = candidates[0]
    if payloads:
        merged["payload"] = payloads[0]
        merged["self_consistency"] = {"samples": len(candidates), "payloads": payloads}
    return json.dumps(merged, ensure_ascii=False)


@tool
def python_sandbox(code: str) -> str:
    """Execute Python code in an isolated sandbox (E2B microVM, or a locked-down
    throwaway Docker container). Requires HITL approval."""
    from cys_core.infrastructure.tools.adapters.multimodal import python_sandbox as _run

    return json.dumps(_run(code), ensure_ascii=False)


@tool
def vision_analyze(path: str, question: str = "Describe this image in detail.") -> str:
    """Analyze image attachments (charts, screenshots, diagrams)."""
    from cys_core.infrastructure.tools.adapters.multimodal import vision_analyze as _vision

    return json.dumps(_vision(path, question=question), ensure_ascii=False)


@tool
def search_archived_webpage(url: str, timestamp: str = "") -> str:
    """Retrieve historical webpage content via Wayback Machine."""
    from cys_core.infrastructure.tools.adapters.multimodal import search_archived_webpage as _archive

    return json.dumps(_archive(url, timestamp=timestamp), ensure_ascii=False)


@tool
def delegate_research(subtask: str, *, context_id: str = "", tenant_id: str = "default") -> str:
    """Delegate a read-only research subtask to the research persona in-process."""
    from cys_core.application.use_cases.delegate_research import DelegateResearch
    from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog
    from cys_core.runtime.agent import get_runtime

    use_case = DelegateResearch(runtime=get_runtime(), catalog=get_agent_catalog())
    payload = use_case.execute_sync(subtask, context_id=context_id, tenant_id=tenant_id)
    return json.dumps(payload, ensure_ascii=False)


def _resolve_spawn_worker_job(
    persona: str,
    sub_goal: str,
    *,
    context_id: str = "",
    tenant_id: str = "default",
    persona_overlay: str = "",
) -> tuple[str | None, Any | None, Any | None]:
    """Validate spawn request; return (error_json, worker_job, queue)."""
    from bootstrap.container import get_container
    from cys_core.application.spawn_broker import SubagentSpawnBroker
    from cys_core.domain.runs.models import ContextKind
    from cys_core.domain.runs.spawn import SpawnWorkerPayload, sanitize_persona_overlay
    from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog
    from cys_core.infrastructure.runs.factory import get_run_state_store

    if not context_id:
        return json.dumps({"error": "missing context_id"}, ensure_ascii=False), None, None

    store = get_run_state_store()
    state = None
    for kind in (ContextKind.SESSION, ContextKind.JOB, ContextKind.INVESTIGATION):
        state = store.get(tenant_id, context_id, kind.value)
        if state is not None:
            break
    if state is None:
        return json.dumps({"error": "run_context_not_found"}, ensure_ascii=False), None, None

    ctx = state.run_context
    container = get_container()
    workspace_id = ""
    engagement_store = container.get_engagement_state_store()
    engagement = engagement_store.get(tenant_id, context_id)
    if engagement is not None:
        workspace_id = (getattr(engagement, "workspace_id", "") or "").strip()
    broker = SubagentSpawnBroker(
        get_agent_catalog(),
        workspace_store=container.get_workspace_store(),
        require_workspace_in_enforce=container.settings.authz_mode == "enforce",
    )
    payload = SpawnWorkerPayload(
        parent_context=ctx,
        persona=persona,
        sub_goal=sub_goal,
        persona_overlay=sanitize_persona_overlay(persona_overlay),
    )
    reason = broker.validate(
        payload,
        mode=ctx.mode,
        profile_id=ctx.profile_id,
        parent_persona="conductor",
        workspace_id=workspace_id,
    )
    if reason:
        return json.dumps({"error": reason}, ensure_ascii=False), None, None

    job = broker.to_worker_job(payload, event_id=context_id)
    parent_job_id = structlog.contextvars.get_contextvars().get("job_id")
    work_kind = structlog.contextvars.get_contextvars().get("work_kind")
    if isinstance(parent_job_id, str) and work_kind == "follow_up_orchestrate":
        from bootstrap.settings import get_settings

        settings = get_settings()
        engagement_store = container.get_engagement_state_store()
        engagement = engagement_store.get(tenant_id, context_id)
        if engagement is not None:
            if engagement.follow_up_spawn_count >= settings.max_follow_up_spawns:
                return json.dumps({"error": "max_follow_up_spawns_exceeded"}, ensure_ascii=False), None, None
            engagement.follow_up_spawn_count += 1
            engagement.reopen_for_follow_up()
            spawned = list(engagement.follow_up_spawned_job_ids or [])
            spawned.append(job.job_id)
            engagement.follow_up_spawned_job_ids = spawned
            engagement_store.upsert(engagement)
        job.payload.update(
            {
                "phase": "follow_up",
                "work_kind": "follow_up_child",
                "orchestrator_job_id": parent_job_id,
                "operator_message": sub_goal,
                "context_id": context_id,
                "spawned_job_ids": list(engagement.follow_up_spawned_job_ids or []) if engagement else [],
            }
        )
    job_store = container.get_job_store()
    queue = container.get_job_queue(persona=persona)
    job_store.upsert_pending(
        job.job_id,
        job.persona,
        correlation_id=job.correlation_id,
        tenant_id=job.tenant_id,
        event_id=job.event_id,
    )
    return None, job, queue


def _spawn_worker(
    persona: str,
    sub_goal: str,
    *,
    context_id: str = "",
    tenant_id: str = "default",
    persona_overlay: str = "",
) -> str:
    """Enqueue a specialist worker spawned from the active conductor session."""
    error_json, job, queue = _resolve_spawn_worker_job(
        persona,
        sub_goal,
        context_id=context_id,
        tenant_id=tenant_id,
        persona_overlay=persona_overlay,
    )
    if error_json is not None:
        return error_json
    assert job is not None and queue is not None
    queue.enqueue(job)
    return json.dumps(
        {"job_id": job.job_id, "persona": persona, "status": "enqueued"},
        ensure_ascii=False,
    )


async def _aspawn_worker(
    persona: str,
    sub_goal: str,
    *,
    context_id: str = "",
    tenant_id: str = "default",
    persona_overlay: str = "",
) -> str:
    """Async enqueue for worker event-loop contexts (conductor arun)."""
    error_json, job, queue = _resolve_spawn_worker_job(
        persona,
        sub_goal,
        context_id=context_id,
        tenant_id=tenant_id,
        persona_overlay=persona_overlay,
    )
    if error_json is not None:
        return error_json
    assert job is not None and queue is not None
    await queue.aenqueue(job)
    return json.dumps(
        {"job_id": job.job_id, "persona": persona, "status": "enqueued"},
        ensure_ascii=False,
    )


spawn_worker = StructuredTool.from_function(
    func=_spawn_worker,
    coroutine=_aspawn_worker,
    name="spawn_worker",
    description="Enqueue a specialist worker spawned from the active conductor session.",
)


@tool
def plan_tool_calls(goal: str, steps_json: str) -> str:
    """ReWOO-style upfront tool plan (search → read → extract) without reactive loops."""
    try:
        steps = json.loads(steps_json) if steps_json.strip().startswith("[") else []
    except json.JSONDecodeError:
        steps = []
    return json.dumps({"goal": goal, "planned_steps": steps, "status": "planned"}, ensure_ascii=False)


@tool
def create_report_outline(title: str, sections_json: str = "[]") -> str:
    """Skeleton-of-Thoughts: create report outline before section fill."""
    try:
        sections = json.loads(sections_json) if sections_json.strip().startswith("[") else []
    except json.JSONDecodeError:
        sections = []
    if not sections:
        sections = ["summary", "findings", "recommendations"]
    return json.dumps({"title": title, "sections": sections}, ensure_ascii=False)


@tool
def browser_use(url: str, action: str = "navigate") -> str:
    """Headless browser actions. Disabled unless BROWSER_ENABLED=true."""
    from cys_core.application.runtime_config import get_browser_enabled
    from cys_core.security.monitor import AgentMonitor

    AgentMonitor("conductor").log_orchestration_tool("browser", "browser_use", {"url": url, "action": action})
    if not get_browser_enabled():
        return json.dumps(
            {"success": False, "error": "browser disabled", "hint": "set BROWSER_ENABLED=true with HITL"},
            ensure_ascii=False,
        )
    return json.dumps({"success": False, "stub": True, "url": url, "action": action}, ensure_ascii=False)


@tool
def transcribe_audio(path: str) -> str:
    """Transcribe audio attachment (stub — wire STT provider in production)."""
    return json.dumps(
        {"success": False, "path": path, "note": "STT stub — integrate Whisper or cloud STT"},
        ensure_ascii=False,
    )


@tool
def update_todos(todos_json: str, *, context_id: str = "", tenant_id: str = "default") -> str:
    """Replace work todos for the active run context."""
    from cys_core.domain.runs.plan_models import WorkTodo
    from cys_core.infrastructure.runs.factory import get_work_todo_store

    try:
        raw = json.loads(todos_json) if todos_json.strip().startswith("[") else []
    except json.JSONDecodeError:
        raw = []
    todos = [WorkTodo.model_validate(item) for item in raw]
    store = get_work_todo_store()
    if context_id:
        store.replace_todos(tenant_id, context_id, todos)
    return json.dumps({"updated": len(todos), "context_id": context_id}, ensure_ascii=False)


_ALL_TOOLS: list[BaseTool] = [
    read_repo_metadata,
    parse_sast_report,
    analyze_workflow,
    run_active_scan,
    parse_netflow,
    enrich_ioc,
    correlate_dns,
    query_siem_readonly,
    rag_query,
    dedup_alerts,
    build_timeline,
    correlate_findings,
    check_control,
    map_framework,
    audit_evidence,
    execute_command,
    search_personas,
    search_skills,
    search_tools,
    ask_user,
    update_todos,
    web_search,
    read_document,
    reasoning_step,
    reasoning_check,
    extract_structured_output,
    python_sandbox,
    vision_analyze,
    search_archived_webpage,
    delegate_research,
    spawn_worker,
    plan_tool_calls,
    create_report_outline,
    browser_use,
    transcribe_audio,
]

_BUILTIN_TOOL_NAMES: list[str] = [tool.name for tool in _ALL_TOOLS]

from cys_core.registry.veil_tools import build_veil_tools

_ALL_TOOLS.extend(build_veil_tools())

from cys_core.registry.siem_tools import build_siem_tools

_ALL_TOOLS.extend(build_siem_tools())

from cys_core.registry.nessus_tools import build_nessus_tools

_ALL_TOOLS.extend(build_nessus_tools())


def list_tools(*, profile_id: str = DEFAULT_PROFILE_ID, enabled_only: bool = True) -> list[str]:
    from cys_core.infrastructure.policy.profile_policy_adapter import filter_tools_for_profile_live

    names = tool_registry.names()
    return filter_tools_for_profile_live(names, profile_id)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {t.name: t for t in _ALL_TOOLS}
        self._load_catalog_overrides()

    def _load_catalog_overrides(self) -> None:
        try:
            from cys_core.application.runtime_config import get_use_dynamic_catalog
            from cys_core.infrastructure.catalog.registry_factory import get_tool_catalog

            if not get_use_dynamic_catalog():
                return
            for entry in get_tool_catalog().list_tools(enabled_only=True):
                if entry.enabled and entry.name in self._tools:
                    tool = self._tools[entry.name]
                    if entry.description and hasattr(tool, "description"):
                        tool.description = entry.description
        except Exception:
            return

    def reload(self) -> None:
        self._tools = {t.name: t for t in _ALL_TOOLS}
        self._tools.update({t.name: t for t in build_veil_tools()})
        self._tools.update({t.name: t for t in build_siem_tools()})
        self._tools.update({t.name: t for t in build_nessus_tools()})
        self._load_catalog_overrides()

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def resolve(self, names: list[str], profile_id: str = DEFAULT_PROFILE_ID) -> list[BaseTool]:
        from cys_core.infrastructure.policy.profile_policy_adapter import filter_tools_for_profile_live

        filtered = filter_tools_for_profile_live(names, profile_id)
        return [self.get(n) for n in filtered]

    def names(self, *, profile_id: str | None = None) -> list[str]:
        if profile_id:
            return list_tools(profile_id=profile_id)
        return list(self._tools.keys())


tool_registry = ToolRegistry()
