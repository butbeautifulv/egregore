from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent

from cys_core.application.ports import PersistenceContext
from cys_core.llm import get_model
from cys_core.persistence import get_persistence_connector
from cys_core.registry.agents import get_agent_registry
from cys_core.registry.product_context import get_product_context
from cys_core.registry.tools import tool_registry
from cys_core.runtime.agent import get_runtime, make_assessment_pipeline_tool, make_async_assessment_pipeline_tool


def create_assessment_coordinator(persistence: PersistenceContext | None = None, *, async_tools: bool = False):
    """Create Deep Agent coordinator with security subagents from registry."""
    stack = persistence or get_persistence_connector().open()
    registry = get_agent_registry()
    runtime = get_runtime()
    coordinator = registry.get("coordinator")

    subagent_defs = registry.by_role("specialist") + [registry.get("critic")]
    subagents = [runtime.to_deep_agent_subagent(defn) for defn in subagent_defs]

    pipeline_tool = make_async_assessment_pipeline_tool(runtime) if async_tools else make_assessment_pipeline_tool(runtime)
    coordinator_tools = [pipeline_tool, tool_registry.get("run_active_scan")]

    interrupt_on = coordinator.interrupt_on or {
        "write_file": True,
        "run_active_scan": True,
        "run_assessment_pipeline": False,
    }

    return create_deep_agent(
        model=get_model(),
        system_prompt=coordinator.system_prompt,
        tools=coordinator_tools,
        subagents=subagents,
        interrupt_on=interrupt_on,
        checkpointer=stack.checkpointer,
        store=stack.store,
        skills=[f"./{get_product_context().skills_path}/"],
        name="cys-coordinator",
    )


async def create_assessment_coordinator_async(persistence: PersistenceContext | None = None):
    """Create Deep Agent coordinator with async persistence and tools."""
    stack = persistence or await get_persistence_connector().open_async()
    registry = get_agent_registry()
    runtime = get_runtime()
    coordinator = registry.get("coordinator")

    subagent_defs = registry.by_role("specialist") + [registry.get("critic")]
    subagents = [runtime.to_deep_agent_subagent(defn) for defn in subagent_defs]

    coordinator_tools = [make_async_assessment_pipeline_tool(runtime), tool_registry.get("run_active_scan")]
    interrupt_on = coordinator.interrupt_on or {
        "write_file": True,
        "run_active_scan": True,
        "run_assessment_pipeline": False,
    }

    return create_deep_agent(
        model=get_model(),
        system_prompt=coordinator.system_prompt,
        tools=coordinator_tools,
        subagents=subagents,
        interrupt_on=interrupt_on,
        checkpointer=stack.checkpointer,
        store=stack.store,
        skills=[f"./{get_product_context().skills_path}/"],
        name="cys-coordinator",
    )


def run_session(
    goal: str,
    *,
    thread_id: str = "session-001",
    persistence: PersistenceContext | None = None,
) -> dict[str, Any]:
    """Run a long-running Deep Agent assessment session."""
    agent = create_assessment_coordinator(persistence)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": goal}]},
        config=config,
    )
    return dict(result)


async def run_session_async(
    goal: str,
    *,
    thread_id: str = "session-001",
    persistence: PersistenceContext | None = None,
) -> dict[str, Any]:
    """Run a long-running Deep Agent assessment session from async callers."""
    agent = await create_assessment_coordinator_async(persistence)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": goal}]},
        config=config,
    )
    return dict(result)
