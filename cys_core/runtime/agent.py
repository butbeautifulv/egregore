from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Callable, TypeVar

from langchain.agents import create_agent
from langchain.agents.middleware.human_in_the_loop import HumanInTheLoopMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.types import Command
from pydantic import BaseModel

from cys_core.application.runtime_config import (
    get_context_summary_enabled,
    get_egregore_one_tool_per_turn,
    get_keep_tool_results,
    get_sgr_default_mode,
    get_stage,
    get_use_sgr_reasoning,
)
from cys_core.domain.catalog.profile_id import DEFAULT_PROFILE_ID
from cys_core.domain.security.profile_tools import filter_tools_for_profile
from cys_core.llm import get_default_recursion_limit
from cys_core.application.ports import ModelConnector, PersistenceContext
from cys_core.domain.agents.policies import build_interrupt_on
from cys_core.domain.memory.services import MemoryReadService
from cys_core.domain.messaging import extract_message_content
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer, get_output_guardrails
from cys_core.domain.security.prompt_context import REFUSAL_MESSAGE
from cys_core.domain.workers.job_budget import JobBudgetExceeded, JobBudgetTracker
from cys_core.llm import get_model_connector
from cys_core.middleware.context_summary_middleware import ContextSummaryMiddleware
from cys_core.middleware.memory_context_middleware import MemoryContextMiddleware
from cys_core.middleware.one_tool_middleware import OneToolPerTurnMiddleware
from cys_core.middleware.prompt_context_middleware import PromptContextMiddleware
from cys_core.middleware.scope_middleware import ScopeMiddleware
from cys_core.middleware.security_middleware import SecurityMiddleware
from cys_core.middleware.tool_coercion_middleware import ToolCoercionMiddleware
from cys_core.observability.trace_attributes import merge_langchain_config
from cys_core.observability.metrics import metrics
from cys_core.registry.agents import AgentDefinition, AgentRegistry, get_agent_registry
from cys_core.registry.schemas import schema_registry
from cys_core.registry.tools import tool_registry

T = TypeVar("T", bound=BaseModel)


def _structured_has_content(data: dict[str, Any]) -> bool:
    for value in data.values():
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, (int, float)) and value not in (0, 0.0):
            return True
    return False


def _parse_json_text(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        fenced = "\n".join(lines).strip()
        try:
            parsed = json.loads(fenced)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _default_sync_persistence() -> PersistenceContext:
    from cys_core.application.ports.persistence_provider import get_sync_persistence

    return get_sync_persistence()


async def _default_async_persistence() -> PersistenceContext:
    from cys_core.application.ports.persistence_provider import get_async_persistence

    return await get_async_persistence()


def _default_memory_reader() -> MemoryReadService | None:
    from cys_core.infrastructure.memory.factory import get_memory_read_service

    return get_memory_read_service()


class AgentRuntime:
    """Single entry point for creating and running config-driven agents."""

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        model_connector: ModelConnector | None = None,
        *,
        persistence_context: PersistenceContext | None = None,
        async_persistence_provider: Callable[[], Any] | None = None,
        sync_persistence_provider: Callable[[], PersistenceContext] | None = None,
        memory_reader: MemoryReadService | None = None,
    ) -> None:
        self.registry = registry or get_agent_registry()
        self.model_connector = model_connector or get_model_connector()
        self.sanitizer = get_input_sanitizer()
        self.guardrails = get_output_guardrails()
        self._persistence_context = persistence_context
        self._sync_persistence_provider = sync_persistence_provider or _default_sync_persistence
        self._async_persistence_provider = async_persistence_provider or _default_async_persistence
        self._memory_reader = memory_reader if memory_reader is not None else _default_memory_reader()

    def _sync_persistence(self) -> PersistenceContext:
        if self._persistence_context is not None:
            return self._persistence_context
        return self._sync_persistence_provider()

    async def _async_persistence(self) -> PersistenceContext:
        if self._persistence_context is not None:
            return self._persistence_context
        return await self._async_persistence_provider()

    def _build_middleware(
        self,
        defn: AgentDefinition,
        session_id: str,
        *,
        tenant_id: str = "default",
        investigation_id: str = "",
        goal: str = "",
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> list[Any]:
        middleware: list[Any] = [
            PromptContextMiddleware(
                agent_id=defn.name,
                system_prompt_digest=defn.system_prompt_digest,
                session_id=session_id,
                sanitizer=self.sanitizer,
                guardrails=self.guardrails,
            ),
        ]
        if self._memory_reader is not None and investigation_id:
            middleware.append(
                MemoryContextMiddleware(
                    self._memory_reader,
                    tenant_id=tenant_id,
                    investigation_id=investigation_id,
                )
            )
        if get_context_summary_enabled():
            from cys_core.infrastructure.context.factory import get_context_summarizer

            middleware.append(
                ContextSummaryMiddleware(
                    get_context_summarizer(),
                    goal=goal,
                    keep_tool_results=get_keep_tool_results(),
                )
            )
        middleware.extend(
            [
                ScopeMiddleware(allowed_tools=defn.allowed_tools),
                ToolCoercionMiddleware(),
                SecurityMiddleware(agent_id=defn.name, session_id=session_id, profile_id=profile_id),
            ]
        )
        interrupt_on = build_interrupt_on(defn.hitl_tools)
        if interrupt_on:
            middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

        from cys_core.application.policy_resolver import get_profile_policy_resolver
        from cys_core.application.reasoning.sgr_policy import resolve_sgr_policy
        from cys_core.middleware.sgr_one_tool_middleware import SgrOneToolMiddleware
        from cys_core.middleware.sgr_reasoning_middleware import SchemaGuidedReasoningMiddleware
        from cys_core.middleware.sgr_session import SgrSessionState

        profile_policy = get_profile_policy_resolver().policy(profile_id)
        sgr = resolve_sgr_policy(
            profile_policy=profile_policy,
            agent=defn,
            use_sgr_reasoning=get_use_sgr_reasoning(),
            default_mode=get_sgr_default_mode(),  # type: ignore[arg-type]
        )
        if sgr.enabled:
            session = SgrSessionState()
            middleware.append(SchemaGuidedReasoningMiddleware(policy=sgr, session=session))
            middleware.append(SgrOneToolMiddleware(session=session))
        elif get_egregore_one_tool_per_turn():
            middleware.append(OneToolPerTurnMiddleware())
        return middleware

    def create(
        self,
        defn: AgentDefinition,
        *,
        model: BaseChatModel | None = None,
        session_id: str = "default",
        use_checkpointer: bool = True,
        extra_tools: list | None = None,
        tenant_id: str = "default",
        investigation_id: str = "",
        profile_id: str = DEFAULT_PROFILE_ID,
        goal: str = "",
    ):
        tool_names = filter_tools_for_profile(defn.tools, profile_id)
        # Ensure reasoning_step is available when SGR is enabled by resolved policy.
        try:
            from cys_core.application.policy_resolver import get_profile_policy_resolver
            from cys_core.application.reasoning.sgr_policy import resolve_sgr_policy
            from cys_core.domain.reasoning.sgr_models import REASONING_STEP_TOOL

            profile_policy = get_profile_policy_resolver().policy(profile_id)
            sgr = resolve_sgr_policy(
                profile_policy=profile_policy,
                agent=defn,
                use_sgr_reasoning=get_use_sgr_reasoning(),
                default_mode=get_sgr_default_mode(),  # type: ignore[arg-type]
            )
            if getattr(sgr, "enabled", False) and REASONING_STEP_TOOL not in tool_names:
                tool_names = [REASONING_STEP_TOOL, *tool_names]
        except Exception:
            pass
        tools = tool_registry.resolve(tool_names, profile_id=profile_id)
        if extra_tools:
            tools = [*tools, *extra_tools]
        if defn.skills:
            from cys_core.registry.skills_tool import make_load_skill_tool

            tools.append(make_load_skill_tool(defn.skills, persona=defn.name, job_id=session_id))

        persistence = self._sync_persistence()
        checkpointer = persistence.checkpointer if use_checkpointer else None
        store = persistence.store if use_checkpointer else None

        schema = schema_registry.get(defn.schema_name)
        return create_agent(
            model=model or self.model_connector.create_model(),
            tools=tools,
            system_prompt=defn.system_prompt,
            middleware=self._build_middleware(
                defn,
                session_id,
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                goal=goal or investigation_id,
                profile_id=profile_id,
            ),
            response_format=schema,
            checkpointer=checkpointer,
            store=store,
            name=defn.name,
        )

    async def acreate(
        self,
        defn: AgentDefinition,
        *,
        model: BaseChatModel | None = None,
        session_id: str = "default",
        use_checkpointer: bool = True,
        extra_tools: list | None = None,
        sandbox_tools: list | None = None,
        tenant_id: str = "default",
        investigation_id: str = "",
        profile_id: str = DEFAULT_PROFILE_ID,
        goal: str = "",
    ):
        if sandbox_tools is not None:
            tools = sandbox_tools
        else:
            tool_names = filter_tools_for_profile(defn.tools, profile_id)
            tools = tool_registry.resolve(tool_names, profile_id=profile_id)
            if extra_tools:
                tools = [*tools, *extra_tools]
            if defn.skills:
                from cys_core.registry.skills_tool import make_load_skill_tool

                tools.append(make_load_skill_tool(defn.skills, persona=defn.name, job_id=session_id))

        persistence = await self._async_persistence()
        checkpointer = persistence.checkpointer if use_checkpointer else None
        store = persistence.store if use_checkpointer else None

        schema = schema_registry.get(defn.schema_name)
        return create_agent(
            model=model or self.model_connector.create_model(),
            tools=tools,
            system_prompt=defn.system_prompt,
            middleware=self._build_middleware(
                defn,
                session_id,
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                goal=goal or investigation_id,
                profile_id=profile_id,
            ),
            response_format=schema,
            checkpointer=checkpointer,
            store=store,
            name=defn.name,
        )

    def run(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        tenant_id: str = "default",
        investigation_id: str = "",
    ) -> dict[str, Any]:
        defn = self.registry.get(name)
        sid = session_id or f"agent-{name}"
        agent = self.create(
            defn,
            session_id=sid,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
        )
        schema = schema_registry.get(defn.schema_name)
        return self._invoke(
            agent,
            user_input,
            session_id=sid,
            schema=schema,
            agent_id=name,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
        )

    async def arun(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
        sandbox_tools: list | None = None,
        recursion_limit: int | None = None,
        job_id: str = "",
        event_id: str = "",
        correlation_id: str = "",
        tenant_id: str = "default",
        investigation_id: str = "",
        sandbox_id: str = "",
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> dict[str, Any]:
        defn = self.registry.get(name)
        sid = session_id or f"agent-{name}"
        inv_id = investigation_id or correlation_id or event_id
        entries_loaded = 0
        if self._memory_reader is not None and inv_id:
            entries_loaded = len(
                self._memory_reader.query_investigation(tenant_id, inv_id, limit=10, requesting_tenant_id=tenant_id)
            )
        profile_id = profile_id or DEFAULT_PROFILE_ID
        agent = await self.acreate(
            defn,
            session_id=sid,
            sandbox_tools=sandbox_tools,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            profile_id=profile_id,
            goal=user_input,
        )
        schema = schema_registry.get(defn.schema_name)
        return await self._ainvoke(
            agent,
            user_input,
            session_id=sid,
            schema=schema,
            recursion_limit=recursion_limit,
            agent_id=defn.name,
            job_id=job_id,
            event_id=event_id,
            correlation_id=correlation_id,
            investigation_id=inv_id,
            tenant_id=tenant_id,
            sandbox_id=sandbox_id,
            memory_entries_loaded=entries_loaded,
        )

    async def aresume(self, name: str, session_id: str, resume: dict[str, Any]) -> dict[str, Any]:
        defn = self.registry.get(name)
        agent = await self.acreate(defn, session_id=session_id)
        schema = schema_registry.get(defn.schema_name)
        config = merge_langchain_config(
            {
                "configurable": {"thread_id": session_id},
                "callbacks": self.model_connector.callbacks(),
                "recursion_limit": 25,
            },
            persona=name,
            session_id=session_id,
            trace_name=f"egregore-{name}-resume",
        )
        result = await agent.ainvoke(Command(resume=resume), config=config)
        return self._coerce_result(result, schema=schema)

    def _invoke(
        self,
        agent,
        user_input: str,
        *,
        session_id: str,
        schema: type[BaseModel] | None,
        agent_id: str = "",
        tenant_id: str = "default",
        investigation_id: str = "",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        try:
            sanitized = self.sanitizer.sanitize(user_input, source="user")
        except SecurityViolation:
            return {"error": REFUSAL_MESSAGE}
        JobBudgetTracker.record_tokens(session_id, JobBudgetTracker.estimate_tokens(sanitized))
        config = merge_langchain_config(
            {
                "configurable": {"thread_id": session_id},
                "callbacks": self.model_connector.callbacks(),
                "recursion_limit": 25,
            },
            persona=agent_id or "agent",
            session_id=session_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            correlation_id=correlation_id,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": sanitized}]},
            config=config,
        )
        return self._coerce_result(result, schema=schema)

    async def _ainvoke(
        self,
        agent,
        user_input: str,
        *,
        session_id: str,
        schema: type[BaseModel] | None,
        recursion_limit: int | None = None,
        agent_id: str = "",
        job_id: str = "",
        event_id: str = "",
        correlation_id: str = "",
        investigation_id: str = "",
        tenant_id: str = "default",
        sandbox_id: str = "",
        memory_entries_loaded: int = 0,
    ) -> dict[str, Any]:
        try:
            sanitized = self.sanitizer.sanitize(user_input, source="user")
        except SecurityViolation:
            metrics.record_sanitizer_block("user", "hard")
            return {"error": REFUSAL_MESSAGE}
        JobBudgetTracker.record_tokens(session_id, JobBudgetTracker.estimate_tokens(sanitized))
        config = merge_langchain_config(
            {
                "configurable": {"thread_id": session_id},
                "callbacks": self.model_connector.callbacks(),
                "recursion_limit": recursion_limit or get_default_recursion_limit(),
            },
            persona=agent_id or session_id,
            job_id=job_id,
            event_id=event_id,
            correlation_id=correlation_id,
            investigation_id=investigation_id,
            session_id=session_id,
            tenant_id=tenant_id,
            sandbox_id=sandbox_id,
            memory_entries_loaded=memory_entries_loaded,
        )
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": sanitized}]},
                config=config,
            )
        except JobBudgetExceeded as exc:
            return {"error": str(exc)}
        coerced = self._coerce_result(result, schema=schema)
        try:
            JobBudgetTracker.record_tokens(
                session_id,
                JobBudgetTracker.estimate_tokens(json.dumps(coerced, ensure_ascii=False)),
            )
        except JobBudgetExceeded as exc:
            return {"error": str(exc)}
        return coerced

    def _coerce_result(
        self,
        result: dict[str, Any],
        *,
        schema: type[BaseModel] | None,
    ) -> dict[str, Any]:
        structured = result.get("structured_response")
        if structured is not None:
            data = structured.model_dump() if isinstance(structured, BaseModel) else dict(structured)
            if _structured_has_content(data):
                if schema:
                    validated = self.guardrails.validate_schema(data, schema)
                    return validated.model_dump()
                return data

        messages = result.get("messages", [])
        if not messages:
            return {"error": "no response"}
        text = extract_message_content(messages[-1].content)
        data = _parse_json_text(text)
        if data is None:
            return {"raw_response": text}

        if schema:
            try:
                validated = self.guardrails.validate_schema(data, schema)
                return validated.model_dump()
            except SecurityViolation:
                if get_stage() == "dev":
                    return data
                raise
        return self.guardrails.validate_output({"response": json.dumps(data, ensure_ascii=False)})

    def to_deep_agent_subagent(self, defn: AgentDefinition) -> dict[str, Any]:
        return {
            "name": defn.name,
            "description": defn.description,
            "system_prompt": defn.system_prompt,
            "tools": tool_registry.resolve(defn.tools),
        }


@lru_cache
def get_runtime() -> AgentRuntime:
    return AgentRuntime()
