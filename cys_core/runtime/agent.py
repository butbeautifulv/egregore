from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, TypeVar

from langchain.agents import create_agent
from langchain.agents.middleware.human_in_the_loop import HumanInTheLoopMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.types import Command
from pydantic import BaseModel

from bootstrap.settings import settings
from cys_core.application.ports import ModelConnector
from cys_core.domain.agents.policies import build_interrupt_on
from cys_core.domain.messaging import extract_message_content
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.factory import get_input_sanitizer, get_output_guardrails
from cys_core.domain.security.prompt_context import REFUSAL_MESSAGE
from cys_core.domain.workers.job_budget import JobBudgetExceeded, JobBudgetTracker
from cys_core.llm import get_model_connector
from cys_core.middleware.prompt_context_middleware import PromptContextMiddleware
from cys_core.middleware.scope_middleware import ScopeMiddleware
from cys_core.middleware.security_middleware import SecurityMiddleware
from cys_core.observability.langfuse_tags import merge_langchain_config
from cys_core.observability.metrics import metrics
from cys_core.persistence import get_persistence_connector
from cys_core.registry.agents import AgentDefinition, AgentRegistry, get_agent_registry
from cys_core.registry.schemas import schema_registry
from cys_core.registry.tools import tool_registry

T = TypeVar("T", bound=BaseModel)


class AgentRuntime:
    """Single entry point for creating and running config-driven agents."""

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        model_connector: ModelConnector | None = None,
    ) -> None:
        self.registry = registry or get_agent_registry()
        self.model_connector = model_connector or get_model_connector()
        self.sanitizer = get_input_sanitizer()
        self.guardrails = get_output_guardrails()

    def _build_middleware(self, defn: AgentDefinition, session_id: str) -> list[Any]:
        middleware: list[Any] = [
            PromptContextMiddleware(
                agent_id=defn.name,
                system_prompt_digest=defn.system_prompt_digest,
                session_id=session_id,
                sanitizer=self.sanitizer,
                guardrails=self.guardrails,
            ),
            ScopeMiddleware(allowed_tools=defn.allowed_tools),
            SecurityMiddleware(agent_id=defn.name, session_id=session_id),
        ]
        interrupt_on = build_interrupt_on(defn.hitl_tools)
        if interrupt_on:
            middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))
        return middleware

    def create(
        self,
        defn: AgentDefinition,
        *,
        model: BaseChatModel | None = None,
        session_id: str = "default",
        use_checkpointer: bool = True,
        extra_tools: list | None = None,
    ):
        tools = tool_registry.resolve(defn.tools)
        if extra_tools:
            tools = [*tools, *extra_tools]

        checkpointer = None
        if use_checkpointer:
            checkpointer = get_persistence_connector().open(force_memory=True).checkpointer

        schema = schema_registry.get(defn.schema_name)
        return create_agent(
            model=model or self.model_connector.create_model(),
            tools=tools,
            system_prompt=defn.system_prompt,
            middleware=self._build_middleware(defn, session_id),
            response_format=schema,
            checkpointer=checkpointer,
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
    ):
        if sandbox_tools is not None:
            tools = sandbox_tools
        else:
            tools = tool_registry.resolve(defn.tools)
            if extra_tools:
                tools = [*tools, *extra_tools]

        checkpointer = None
        if use_checkpointer:
            checkpointer = (await get_persistence_connector().open_async(force_memory=True)).checkpointer

        schema = schema_registry.get(defn.schema_name)
        return create_agent(
            model=model or self.model_connector.create_model(),
            tools=tools,
            system_prompt=defn.system_prompt,
            middleware=self._build_middleware(defn, session_id),
            response_format=schema,
            checkpointer=checkpointer,
            name=defn.name,
        )

    def run(
        self,
        name: str,
        user_input: str,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        defn = self.registry.get(name)
        sid = session_id or f"agent-{name}"
        agent = self.create(defn, session_id=sid)
        schema = schema_registry.get(defn.schema_name)
        return self._invoke(agent, user_input, session_id=sid, schema=schema)

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
        sandbox_id: str = "",
    ) -> dict[str, Any]:
        defn = self.registry.get(name)
        sid = session_id or f"agent-{name}"
        agent = await self.acreate(defn, session_id=sid, sandbox_tools=sandbox_tools)
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
            sandbox_id=sandbox_id,
        )

    async def aresume(self, name: str, session_id: str, resume: dict[str, Any]) -> dict[str, Any]:
        defn = self.registry.get(name)
        agent = await self.acreate(defn, session_id=session_id)
        schema = schema_registry.get(defn.schema_name)
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": self.model_connector.callbacks(),
            "recursion_limit": 25,
        }
        result = await agent.ainvoke(Command(resume=resume), config=config)
        return self._coerce_result(result, schema=schema)

    def _invoke(
        self,
        agent,
        user_input: str,
        *,
        session_id: str,
        schema: type[BaseModel] | None,
    ) -> dict[str, Any]:
        try:
            sanitized = self.sanitizer.sanitize(user_input, source="user")
        except SecurityViolation:
            return {"error": REFUSAL_MESSAGE}
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": self.model_connector.callbacks(),
            "recursion_limit": 25,
        }
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
        sandbox_id: str = "",
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
                "recursion_limit": recursion_limit or settings.default_job_recursion_limit,
            },
            persona=agent_id or session_id,
            job_id=job_id,
            event_id=event_id,
            correlation_id=correlation_id,
            sandbox_id=sandbox_id,
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
            if schema:
                validated = self.guardrails.validate_schema(data, schema)
                return validated.model_dump()
            return data

        messages = result.get("messages", [])
        if not messages:
            return {"error": "no response"}
        text = extract_message_content(messages[-1].content)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"raw_response": text}

        if schema:
            try:
                validated = self.guardrails.validate_schema(data, schema)
                return validated.model_dump()
            except SecurityViolation:
                if settings.stage == "dev":
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

