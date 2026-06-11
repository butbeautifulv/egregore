from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, TypeVar

from langchain.agents import create_agent
from langchain.agents.middleware.human_in_the_loop import HumanInTheLoopMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool
from pydantic import BaseModel

from config import settings
from cys_core.llm import get_langfuse_callbacks, get_model
from cys_core.middleware.scope_middleware import ScopeMiddleware
from cys_core.middleware.security_middleware import SecurityMiddleware
from cys_core.persistence import get_async_persistence, get_persistence
from cys_core.registry.agents import AgentDefinition, AgentRegistry, get_agent_registry
from cys_core.registry.schemas import schema_registry
from cys_core.registry.tools import tool_registry
from cys_core.security.guardrails import OutputGuardrails, SecurityViolation
from cys_core.security.sanitizer import InputSanitizer

T = TypeVar("T", bound=BaseModel)

_sanitizer = InputSanitizer()
_guardrails = OutputGuardrails()


class AgentRuntime:
    """Single entry point for creating and running config-driven agents."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self.registry = registry or get_agent_registry()

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
        middleware: list[Any] = [
            ScopeMiddleware(allowed_tools=defn.allowed_tools),
            SecurityMiddleware(agent_id=defn.name, session_id=session_id),
        ]
        if defn.hitl_tools:
            interrupt_on = {
                tool_name: {"allowed_decisions": ["approve", "edit", "reject"]}
                for tool_name, enabled in defn.hitl_tools.items()
                if enabled
            }
            if interrupt_on:
                middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

        checkpointer = None
        if use_checkpointer:
            checkpointer = get_persistence(force_memory=True).checkpointer

        schema = schema_registry.get(defn.schema_name)
        return create_agent(
            model=model or get_model(),
            tools=tools,
            system_prompt=defn.system_prompt,
            middleware=middleware,
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
    ):
        tools = tool_registry.resolve(defn.tools)
        if extra_tools:
            tools = [*tools, *extra_tools]
        middleware: list[Any] = [
            ScopeMiddleware(allowed_tools=defn.allowed_tools),
            SecurityMiddleware(agent_id=defn.name, session_id=session_id),
        ]
        if defn.hitl_tools:
            interrupt_on = {
                tool_name: {"allowed_decisions": ["approve", "edit", "reject"]}
                for tool_name, enabled in defn.hitl_tools.items()
                if enabled
            }
            if interrupt_on:
                middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

        checkpointer = None
        if use_checkpointer:
            checkpointer = (await get_async_persistence(force_memory=True)).checkpointer

        schema = schema_registry.get(defn.schema_name)
        return create_agent(
            model=model or get_model(),
            tools=tools,
            system_prompt=defn.system_prompt,
            middleware=middleware,
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
    ) -> dict[str, Any]:
        defn = self.registry.get(name)
        sid = session_id or f"agent-{name}"
        agent = await self.acreate(defn, session_id=sid)
        schema = schema_registry.get(defn.schema_name)
        return await self._ainvoke(agent, user_input, session_id=sid, schema=schema)

    def _invoke(
        self,
        agent,
        user_input: str,
        *,
        session_id: str,
        schema: type[BaseModel] | None,
    ) -> dict[str, Any]:
        sanitized = _sanitizer.sanitize(user_input)
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": get_langfuse_callbacks(),
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
    ) -> dict[str, Any]:
        sanitized = _sanitizer.sanitize(user_input)
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": get_langfuse_callbacks(),
            "recursion_limit": 25,
        }
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": sanitized}]},
            config=config,
        )
        return self._coerce_result(result, schema=schema)

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
                validated = _guardrails.validate_schema(data, schema)
                return validated.model_dump()
            return data

        messages = result.get("messages", [])
        if not messages:
            return {"error": "no response"}
        content = messages[-1].content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block) for block in content
            )
        try:
            data = json.loads(str(content))
        except json.JSONDecodeError:
            return {"raw_response": str(content)}

        if schema:
            try:
                validated = _guardrails.validate_schema(data, schema)
                return validated.model_dump()
            except SecurityViolation:
                if settings.stage == "dev":
                    return data
                raise
        return _guardrails.validate_output({"response": json.dumps(data, ensure_ascii=False)})

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


def make_assessment_pipeline_tool(runtime: AgentRuntime | None = None):
    """Factory for coordinator tool that runs LangGraph assessment."""
    from cys_core.persistence import get_persistence
    from graph.workflow import run_assessment

    @tool
    def run_assessment_pipeline(input_text: str, thread_id: str = "deep-session") -> str:
        """Run the full LangGraph security assessment pipeline on authorized input."""
        result = run_assessment(
            input_text,
            thread_id=thread_id,
            persistence=get_persistence(force_memory=True),
        )
        return json.dumps(result.get("report") or result, ensure_ascii=False, indent=2)

    return run_assessment_pipeline


def make_async_assessment_pipeline_tool(runtime: AgentRuntime | None = None):
    """Factory for coordinator async tool that runs LangGraph assessment."""
    from cys_core.persistence import get_async_persistence
    from graph.workflow import run_assessment_async

    @tool
    async def run_assessment_pipeline(input_text: str, thread_id: str = "deep-session") -> str:
        """Run the full LangGraph security assessment pipeline on authorized input."""
        result = await run_assessment_async(
            input_text,
            thread_id=thread_id,
            persistence=await get_async_persistence(force_memory=True),
        )
        return json.dumps(result.get("report") or result, ensure_ascii=False, indent=2)

    return run_assessment_pipeline
