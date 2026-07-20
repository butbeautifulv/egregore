from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from cys_core.application.ports.stream_context import StreamContext
from cys_core.application.reasoning.sgr_tooling import resolve_agent_tool_names
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.messaging import extract_message_content
from cys_core.domain.parsing.json_text import parse_json_text
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer, get_output_guardrails
from cys_core.domain.security.prompt_context import REFUSAL_MESSAGE
from cys_core.domain.workers.job_budget import JobBudgetExceeded, JobBudgetTracker
from cys_core.llm import get_model_connector
from cys_core.registry.agents import get_agent_registry
from cys_core.registry.schemas import schema_registry
from cys_core.registry.tools import tool_registry

_DEFAULT_MAX_ITERATIONS = 8


class MinimalReactAgentRunner:
    """Second `AgentRunner` implementation (`cys_core.application.ports.agent_runner.AgentRunner`)
    — proves `AGENT_RUNNER_IMPL`/`configure_agent_runner`'s registry actually lets the agent
    *core* be swapped, not just described (docs/MICROSERVICES_SPLIT_PLAN.md §1 item 2,
    MSP_BACKLOG.md §52.3). Deliberately minimal per that decision: no LangGraph, no
    checkpointer/graph state, no middleware stack (`AgentRuntime._build_middleware`'s
    Scope/ToolDedup/ToolLadder/FollowUp/SGR/ContextSummary/HITL-interrupt middleware) — just a
    hand-written call-model -> maybe-call-tools -> repeat loop, so the seam is proven with zero
    new framework lock-in.

    Still routes every model call through the same swappable `ModelConnector`
    (litellm/model-gateway) and every tool call through the same `tool_registry` (tool-gateway
    PEP, when configured) `AgentRuntime` uses, and still applies the same input sanitizer /
    output guardrails / job-budget tracker — per this project's "switch core to any agent, inside
    a safe system" goal, that security perimeter is meant to live in those shared layers (and one
    level further out, in dispatcher/tool-gateway/model-gateway), not in LangGraph-specific
    middleware, so it isn't lost just because this implementation skips the middleware stack.

    Does NOT support HITL resume (`aresume` always returns an error) — there is no
    interrupt/checkpointer mechanism here to pause on. If a job's persona has any
    `hitl_tools` configured, a tool call matching one is refused outright rather than either
    silently auto-approved or left to block forever — the honest, safe failure mode until the
    cross-process HITL redesign (§1 item 3 / MSP_BACKLOG.md §35) exists.
    """

    def __init__(
        self,
        *,
        registry=None,
        model_connector=None,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._registry = registry or get_agent_registry()
        self._model_connector = model_connector or get_model_connector()
        self._sanitizer = get_input_sanitizer()
        self._guardrails = get_output_guardrails()
        self._max_iterations = max_iterations

    def _resolve_tools(self, defn, profile_id: str, sandbox_tools: list[Any] | None) -> list[Any]:
        if sandbox_tools is not None:
            return sandbox_tools
        tool_names = resolve_agent_tool_names(defn, profile_id)
        return tool_registry.resolve(tool_names, profile_id=profile_id)

    def _finalize(self, response: AIMessage, defn) -> dict[str, Any]:
        text = extract_message_content(response.content)
        data = parse_json_text(text)
        if data is None:
            return {"raw_response": text}
        schema = schema_registry.get(defn.schema_name)
        if schema:
            try:
                validated = self._guardrails.validate_schema(data, schema)
                return validated.model_dump()
            except SecurityViolation:
                return data
        return self._guardrails.validate_output({"response": json.dumps(data, ensure_ascii=False)})

    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        sandbox_tools: list[Any] | None = None,
        job_id: str | None = None,
        event_id: str | None = None,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
        sandbox_id: str | None = None,
        stream_context: StreamContext | None = None,
        recursion_limit: int | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        defn = self._registry.get(name)
        sid = session_id or f"agent-{name}"
        try:
            sanitized = self._sanitizer.sanitize(user_input, source="user")
        except SecurityViolation:
            return {"error": REFUSAL_MESSAGE}

        resolved_profile_id = profile_id or DEFAULT_PROFILE_ID
        tools = self._resolve_tools(defn, resolved_profile_id, sandbox_tools)
        tools_by_name = {tool.name: tool for tool in tools}
        hitl_gated = {tool_name for tool_name, gated in (defn.hitl_tools or {}).items() if gated}

        model = self._model_connector.create_model()
        bound_model = model.bind_tools(tools) if tools else model

        messages: list[Any] = [SystemMessage(content=defn.system_prompt), HumanMessage(content=sanitized)]

        try:
            JobBudgetTracker.record_tokens(sid, JobBudgetTracker.estimate_tokens(sanitized))
            for _ in range(recursion_limit or self._max_iterations):
                response = await bound_model.ainvoke(messages)
                messages.append(response)
                JobBudgetTracker.record_tokens(sid, JobBudgetTracker.estimate_tokens(str(response.content)))
                tool_calls = getattr(response, "tool_calls", None) or []
                if not tool_calls:
                    return self._finalize(response, defn)
                for call in tool_calls:
                    tool_name = call["name"]
                    if tool_name in hitl_gated:
                        return {
                            "error": (
                                f"tool '{tool_name}' requires human approval; "
                                "MinimalReactAgentRunner does not support HITL resume"
                            )
                        }
                    tool = tools_by_name.get(tool_name)
                    if tool is None:
                        content = f"error: unknown tool '{tool_name}'"
                    else:
                        try:
                            result = await tool.ainvoke(call.get("args", {}))
                        except Exception as exc:  # noqa: BLE001 - tool failures become tool-result content, not crashes
                            result = f"error: {exc}"
                        if isinstance(result, str):
                            content = result
                        else:
                            content = json.dumps(result, ensure_ascii=False, default=str)
                    messages.append(ToolMessage(content=content, tool_call_id=call.get("id", "")))
                    JobBudgetTracker.record_tokens(sid, JobBudgetTracker.estimate_tokens(content))
        except JobBudgetExceeded as exc:
            return {"error": str(exc)}

        return {"error": "recursion_limit_exceeded"}

    async def aresume(self, name: str, session_id: str, resume: dict[str, Any]) -> dict[str, Any]:
        return {
            "error": (
                "MinimalReactAgentRunner does not support HITL resume "
                "(no interrupt/checkpointer) — see docs/MICROSERVICES_SPLIT_PLAN.md §1 item 3"
            )
        }
